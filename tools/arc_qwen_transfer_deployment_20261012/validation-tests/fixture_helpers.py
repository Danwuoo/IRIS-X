"""Explicit synthetic adversarial fixture helpers using retained owned output bytes.

Never fabricate production execution. Original artifacts are immutable. Mutations
are test-only, remain tiny_cpu=True, and cannot be accepted by production API.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import zipfile
import validate_transfer_outputs as v

ROOT=Path(__file__).resolve().parents[1]
RETAINED_ROOT=ROOT/'native-transfer-1791808915341057591'
RETAINED_SOURCE=ROOT/'native-test-source-20261012-1241'
RETAINED_ARCHIVE_SHA256='9767add2b294d5371f523d12790fbaf3f1d1241fcfd29a71f898fa4dd62281c0'


def derive_retained_fixture(destination,*,synthetic,mutate=None):
    if synthetic is not True:raise ValueError('explicit synthetic=True required; no production fixture construction')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    if v.file_sha(RETAINED_ROOT/'evidence.zip')!=RETAINED_ARCHIVE_SHA256:raise ValueError('retained original changed')
    with zipfile.ZipFile(RETAINED_ROOT/'evidence.zip') as archive:
        members={n:archive.read(n) for n in archive.namelist() if n!='archive-manifest.json'}
    request=v.strict_json(members['request.json'])
    if request['config'].get('tiny_cpu') is not True:raise ValueError('only actual retained tiny runtime may seed tests')
    terminal=json.loads((RETAINED_ROOT/'terminal-receipt.json').read_bytes())
    if mutate:mutate(members,terminal)
    if v.strict_json(members['request.json'])['config'].get('tiny_cpu') is not True:raise ValueError('test helper cannot relabel synthetic execution')
    manifest={'format':'irisx/qwen14b-probe-archive-v1','files':{n:{'bytes':len(raw),'sha256':v.raw_sha(raw)} for n,raw in sorted(members.items())},'owned_process_closed':True,'public_score':None}
    with zipfile.ZipFile(destination/'evidence.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for n,raw in members.items():archive.writestr(n,raw)
        archive.writestr('archive-manifest.json',v.canonical(manifest))
    terminal['archive'].update(sha256=v.file_sha(destination/'evidence.zip'),bytes=(destination/'evidence.zip').stat().st_size,files=len(members)+1)
    (destination/'terminal-receipt.json').write_bytes(v.canonical(terminal))
    (destination/'SYNTHETIC-FIXTURE.json').write_bytes(v.canonical({'synthetic':True,'format':'irisx/transfer-retained-output-test-fixture-v1','source_evidence_sha256':RETAINED_ARCHIVE_SHA256,'production_evidence':False,'mutated':mutate is not None}))
    return destination


def edit_json(members,name,edit):
    value=v.strict_json(members[name]);edit(value);members[name]=v.canonical(value);return value


def bind_child(members,terminal,edit):
    child=edit_json(members,'child-summary.json',edit);terminal['child']=child


def validate_fixture(path):
    return v.validate_content(path,v.source_identity(RETAINED_SOURCE),source_root=RETAINED_SOURCE,allow_synthetic=True)


class TargetedTTTArchive:
    """Source-aware test adapter. One real tiny case plus explicit other abstentions."""
    def __init__(self,root):
        self.root=Path(root);self.dataset=v.json_file(self.root/'dataset/solver-dataset.json')
        plan=self.dataset['plan'];ids=set(plan['ttt_dev_ids']+plan['ttt_holdout_ids']);actual=v.json_file(self.root/'result.json')['result']
        rows=[actual if c['case_id']==actual['case_id'] else {'case_id':c['case_id'],'complete':False,'answers':[],'reason':'not part of targeted synthetic fixture'} for c in self.dataset['cases'] if c['parent_id'] in ids]
        self.phase={'synthetic':True,'status':'TTT_PARTIAL','denominators':{'dev':8,'holdout':8},'rows':rows}
        self.overrides={}
    def read(self,name):
        if name in self.overrides:return self.overrides[name]
        if name=='experiment/ttt-predictions-sealed.json':return v.canonical(self.phase)
        return v.local_file(self.root/v.safe_name(name),64*1024**2).read_bytes()
    def json(self,name):return v.strict_json(self.read(name))


def make_synthetic_collector_fixture(destination,*,synthetic,template_release=None):
    """Wrap actual owned tiny bytes in explicitly fictional provider/outer receipts.

    This tests only the offline envelope parser. Provider save/download/outer
    ownership are deliberately synthetic, not actual Kaggle execution evidence.
    Production entry rejects this before processing it.
    """
    if synthetic is not True:raise ValueError('explicit synthetic=True required')
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=False)
    release=Path(template_release or ROOT/'preview-005');manifest=v.json_file(release/'publication-manifest.json')
    spec=next(n for n in manifest['notebooks'] if n['role']=='transfer001')
    manifest['synthetic']=True;manifest['fixture_qualification']='Fictional provider/outer envelope around unchanged actual tiny CPU evidence. No production claim.'
    source_mapping=v.source_identity(RETAINED_SOURCE)
    inner=manifest['terminal_contract']['inner_request_source_identity'];inner['mapping']=source_mapping;inner['identity_sha256']=v.digest(source_mapping)
    payload=dest/'code-payload';payload.mkdir()
    with zipfile.ZipFile(payload/'source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name in source_mapping:z.write(RETAINED_SOURCE/name,name)
    code=next(d for d in manifest['datasets'] if d['role']=='code')
    code['upload_inventory']=[{'path':'source.zip','sha256':v.file_sha(payload/'source.zip'),'bytes':(payload/'source.zip').stat().st_size}]
    template=v.normalize_notebook(v.json_file(release/spec['path']));raw=v.canonical(template);(dest/spec['path']).write_bytes(raw);spec.update(sha256=v.raw_sha(raw),bytes=len(raw))
    terminal=v.json_file(RETAINED_ROOT/'terminal-receipt.json');epoch=terminal['predispatch_started_epoch']
    final=deepcopy(template);idx=spec['dispatch_epoch_patch']['cell_index'];final['cells'][idx]['source']=final['cells'][idx]['source'].replace('PREDISPATCH_EPOCH = None','PREDISPATCH_EPOCH = '+repr(epoch))
    final_path=dest/'finalized.ipynb';final_raw=v.canonical(final);final_path.write_bytes(final_raw);constants=v.notebook_constants(final)
    download=dest/'downloads';download.mkdir();prefix=Path(spec['output_root']).name;out=download/prefix;out.mkdir()
    shutil.copyfile(RETAINED_ROOT/'evidence.zip',out/'evidence.zip');shutil.copyfile(RETAINED_ROOT/'terminal-receipt.json',out/'terminal-receipt.json')
    launchroot=download/(prefix+'-launcher');launchroot.mkdir();remote_launcher=spec['output_root']+'-launcher'
    cfg={k.lower():constants[k] for k in ('MANUAL_START','ENABLE_MODEL','PROFILE','OUTPUT_ROOT','SOURCE_PARENT','INPUT_ROOT','CODE_ROOT','DATA_ROOT','TRAINING_ROOT')};cfg.update(session_seconds=43200,probe_seconds=43200,predispatch_epoch=epoch)
    outer_request={'config':cfg,'pins':constants['PINS'],'started_epoch':epoch,'hard_deadline_epoch':epoch+42180,'global_deadline_epoch':epoch+43200,'execution_deadline_epoch':epoch+42000,'provider_deadline_epoch':epoch+42300,'launcher_root':remote_launcher,'loader_sha256':constants['EXPECTED_LOADER_SHA256'],'guard_sha256':constants['EXPECTED_GUARD_SHA256']}
    for name,row in manifest['terminal_contract']['outer_executable_files'].items():
        (launchroot/name).write_bytes((release/row['path']).read_bytes())
    outer_request['driver_sha256']=v.file_sha(launchroot/'bootstrap.py')
    with zipfile.ZipFile(RETAINED_ROOT/'evidence.zip') as z:actual_inner_launch=v.strict_json(z.read('owned-tree/launch.json'))
    worker=actual_inner_launch['coordinator_identity'];supervisor={**worker,'pid':worker['pid']+1000000,'birth':worker['birth']+1}
    proof={'format':'irisx/owned-process-closure-v1','root_identity':supervisor,'scope':'dedicated-subreaper-tree','ownership_complete':True,'closed':True,'owned_identities':[supervisor,worker],'remaining':[],'returncode':0,'worker_returncode':0,'forced':False,'reaped_identities':[supervisor,worker],'errors':[]}
    closure={'format':'irisx/learning-notebook-closure-v1','started_epoch':epoch,'hard_deadline_epoch':epoch+42180,'global_deadline_epoch':epoch+43200,'completed_epoch':terminal['completed_epoch']+1,'within_absolute_deadline':True,'forced':False,'reason':None,'process_tree_proof':proof,'synthetic':True}
    def write(root,name,value):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v.canonical(value))
    write(launchroot,'request.json',outer_request);write(launchroot,'result.json',terminal);write(launchroot,'launcher-closure.json',closure)
    write(launchroot,'owned-tree/closure.json',proof)
    write(launchroot,'owned-tree/launch.json',{'supervisor_identity':supervisor,'worker_argv':['synthetic-python','-I','-B',remote_launcher+'/bootstrap.py',remote_launcher+'/request.json',v.file_sha(launchroot/'request.json')]})
    write(launchroot,'owned-tree/worker-launch.json',{'supervisor_identity':supervisor,'worker_identity':worker})
    write(launchroot,'owned-tree/supervisor-result.json',{'supervisor_identity':supervisor,'root_identity':worker,'closed':True,'ownership_complete':True,'remaining':[],'errors':[],'worker_returncode':0})
    write(dest,'publication-manifest.json',manifest);msha=v.file_sha(dest/'publication-manifest.json')
    clocks={'predispatch_epoch':epoch,'deadline_epoch':epoch+43200,'global_deadline_epoch':epoch+43200,'execution_deadline_epoch':epoch+42000,'outer_deadline_epoch':epoch+42180,'provider_timeout_seconds':42300}
    f={'synthetic':True,'manifest_sha256':msha,'finalized_sha256':v.raw_sha(final_raw),'template_sha256':spec['sha256'],**clocks};write(dest,'finalization.json',f)
    reference=spec['existing_notebook_reference']
    j={'synthetic':True,'role':'transfer001','manifest_sha256':msha,'source_sha256':v.raw_sha(final_raw),'reference':reference,'kernel_id':138123872,'expected_version':21,'save_calls':1,'dispatch_epoch':epoch+1,**clocks};write(dest,'launch-journal.json',j)
    saved={'path':str(final_path.absolute()),'bytes':len(final_raw),'sha256':v.raw_sha(final_raw)}
    l={'synthetic':True,'manifest_sha256':msha,'launch_journal_sha256':v.file_sha(dest/'launch-journal.json'),'finalization_sha256':v.file_sha(dest/'finalization.json'),'reference':reference,'kernel_id':138123872,'version':21,'submitted_source_sha256':v.raw_sha(final_raw),'saved_source':saved,'normalized_source_exact':True};write(dest,'launch-receipt.json',l)
    files=[];listed=[]
    for p in sorted(download.rglob('*')):
        if not p.is_file():continue
        n=p.relative_to(download).as_posix();files.append({'provider_path':n,'local_path':n,'version':21,'numeric_version':21,'bytes':p.stat().st_size,'sha256':v.file_sha(p),'http_status':200,'source_kind':'provider_download'});listed.append({'path':n,'bytes':p.stat().st_size})
    listed.append({'path':prefix+'/checkpoints.zip','bytes':terminal['checkpoint_archive']['bytes']})
    snap={'version':21,'status':'COMPLETE','source_sha256':saved['sha256'],'metadata_sha256':'0'*64}
    retrieval={'synthetic':True,'manifest_sha256':msha,'launch_receipt_sha256':v.file_sha(dest/'launch-receipt.json'),'reference':reference,'kernel_id':138123872,'numeric_output_version':21,'before':snap,'after':snap,'files':files,'provider_files':listed};write(dest,'retrieval-receipt.json',retrieval)
    return {'download_root':download,'manifest':dest/'publication-manifest.json','finalization':dest/'finalization.json','launch_journal':dest/'launch-journal.json','launch_receipt':dest/'launch-receipt.json','retrieval_receipt':retrieval,'finalized_notebook':final_path,'allow_synthetic':True}
