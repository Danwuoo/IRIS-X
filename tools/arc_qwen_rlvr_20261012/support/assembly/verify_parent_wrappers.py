"""Independent archived parent-wrapper replay. No imports of producer/model code.

Caller must authenticate this source, release and expected JIT bytes externally.
Archived PID observations are checked for consistency, never against local /proc.
This establishes the source-bound evidence chain, not remote OS attestation.
"""
from pathlib import Path
import hashlib,json,math,os,stat

CAP=4*1024**2
IDENTITY={'pid','birth','session','state'}
PROOF={'format','root_identity','scope','ownership_complete','closed','owned_identities','remaining','returncode','worker_returncode','forced','reaped_identities','errors'}
SCOPE='dedicated-subreaper-tree'
ENV='/tmp/irisx-qwen14b-rlvr-20261012-environment001'
INTERPRETER_MANIFEST='20a52944f1ee2abf6f47a2e3beafce44951993439fede39335e660cea143495e'
INTERPRETER_ARCHIVE='f937814031eab4698ca6d07ec606ede1825768f3f3e99af76d9db3900bee03c5'


def need(ok,message):
    if not ok:raise ValueError('wrapper: '+message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def read(path,cap=CAP):
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'symlink artifact')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and 0<=before.st_size<=cap,'bounded regular artifact')
        with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(cap+1)
        after=os.fstat(fd);now=path.stat(follow_symlinks=False)
        need(len(raw)==before.st_size and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) and (now.st_dev,now.st_ino)==(before.st_dev,before.st_ino),'artifact changed')
        return raw
    finally:os.close(fd)
def parse(raw):
    def pairs(rows):
        d={}
        for k,v in rows:need(k not in d,'duplicate JSON key');d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('wrapper: nonfinite JSON')))
def obj(path):return parse(read(path))
def closed(d,keys,fmt):need(type(d) is dict and set(d)==set(keys) and d.get('format')==fmt,'closed '+fmt+' schema')
def identity(d):
    need(type(d) is dict and set(d)==IDENTITY and type(d['pid']) is int and d['pid']>0 and type(d['birth']) is int and d['birth']>=0 and type(d['session']) is int and d['session']>0 and type(d['state']) is str and len(d['state'])==1,'process incarnation')
    return (d['pid'],d['birth'],d['session'])
def identities(rows):
    need(type(rows) is list,'identity list');values=[identity(v) for v in rows]
    need(len(set((x[0],x[1]) for x in values))==len(values),'duplicate incarnation')
    return set(values)
def proof(d,supervisor=False):
    closed(d,PROOF|({'supervisor_identity'} if supervisor else set()),'irisx/owned-supervisor-result-v1' if supervisor else 'irisx/owned-process-closure-v1')
    need(d['scope']==SCOPE and type(d['closed']) is bool and type(d['ownership_complete']) is bool and type(d['forced']) is bool,'closure flags')
    for k in ('returncode','worker_returncode'):need(type(d[k]) is int,'terminated return codes')
    need(type(d['errors']) is list and all(type(v) is str for v in d['errors']),'error list')
    all_ids=identities(d['owned_identities']);root=identity(d['root_identity'])
    need(root in all_ids and d['root_identity'] in d['owned_identities'],'exact root membership')
    remaining=identities(d['remaining']);reaped=identities(d['reaped_identities'])
    need(remaining<=all_ids and reaped<=all_ids and not remaining&reaped,'remaining/reaped ownership')
    need(d['owned_identities']==sorted(d['owned_identities'],key=lambda r:(r['birth'],r['pid'])),'owned identity ordering')
    return all_ids


def verify_stage(stage_root,*,expected_argv,epoch,scope):
    """Validate one exact raw stage; clean closure and success are separate axes."""
    root=Path(stage_root);launch=obj(root/'owned-tree/launch.json');worker=obj(root/'owned-tree/worker-launch.json')
    supervisor=obj(root/'owned-tree/supervisor-result.json');p=obj(root/'owned-tree/closure.json');c=obj(root/'closure.json')
    closed(launch,{'format','supervisor_identity','coordinator_identity','worker_argv','scope'},'irisx/owned-process-launch-v1')
    closed(worker,{'format','worker_identity','supervisor_identity','parent_death_signal'},'irisx/owned-worker-launch-v1')
    closed(c,{'format','scope','deadline_epoch','started_epoch','started_monotonic','completed_epoch','completed_monotonic','within_deadline','forced','reason','proof','log_bytes','log_cap_bytes','VM_teardown_or_billing_claim'},'irisx/rlvr-outer-process-closure-v1')
    need(type(epoch) is int and epoch>0 and c['deadline_epoch']==epoch+42180 and type(c['deadline_epoch']) is int,'exact original outer deadline')
    need(c['scope']==scope and launch['scope']==SCOPE and launch['worker_argv']==expected_argv and type(expected_argv) is list and all(type(v) is str for v in expected_argv),'exact argv/scope')
    need(c['proof']==p,'raw closure equals summary proof')
    outer_ids=proof(p);inner_ids=proof(supervisor,True)
    sup=identity(launch['supervisor_identity']);coord=identity(launch['coordinator_identity']);child=identity(worker['worker_identity'])
    need(identity(worker['supervisor_identity'])==identity(supervisor['supervisor_identity'])==identity(p['root_identity'])==sup,'supervisor incarnation chain')
    need(identity(supervisor['root_identity'])==child and supervisor['root_identity']==worker['worker_identity'],'worker incarnation chain')
    need(sup!=coord and child!=sup and child!=coord and child[2]==sup[2]==sup[0] and coord[1]<=sup[1]<=child[1],'dedicated session/birth ordering')
    need(inner_ids<=outer_ids and sup in outer_ids and coord not in outer_ids,'subreaper owned union')
    need(worker['parent_death_signal']==9 and type(worker['parent_death_signal']) is int,'SIGKILL parent-death binding')
    need(supervisor['returncode']==supervisor['worker_returncode']==p['worker_returncode'],'worker return-code chain')
    expected_code=128-p['worker_returncode'] if p['worker_returncode']<0 else p['worker_returncode']
    need(p['returncode']==expected_code or (p['forced'] and p['worker_returncode']==0 and p['returncode']==125),'supervisor return-code mapping')
    need(not supervisor['forced'] or p['forced'],'forced propagation')
    need(type(c['forced']) is bool and type(c['within_deadline']) is bool and c['VM_teardown_or_billing_claim'] is False and (c['reason'] is None or c['reason'] in {'bounded-launcher-log-cap','original-outer-deadline','parent-exception'}),'wrapper flags')
    need(not c['forced'] or p['forced'],'wrapper forced propagation')
    need(c['reason'] is None or c['forced'],'reason requires forced stop')
    for k in ('started_epoch','completed_epoch','started_monotonic','completed_monotonic'):need(finite(c[k]),'finite stage time')
    need(epoch<=c['started_epoch']<=c['completed_epoch'] and 0<=c['started_monotonic']<=c['completed_monotonic'],'ordered stage interval')
    need(not c['within_deadline'] or c['completed_epoch']<=epoch+42180,'within-deadline claim')
    need(abs((c['completed_epoch']-c['started_epoch'])-(c['completed_monotonic']-c['started_monotonic']))<=2,'wall/monotonic stage interval')
    need(type(c['log_bytes']) is int and 0<=c['log_bytes']<=c['log_cap_bytes']==8*1024**2,'bounded log accounting')
    present=[root/n for n in ('stdout.txt','stderr.txt')]
    if all(p.exists() for p in present):need(sum(len(read(p,8*1024**2)) for p in present)==c['log_bytes'],'observed log byte accounting')
    clean=all(x['ownership_complete'] is True and x['closed'] is True and not x['remaining'] and not x['errors'] and not x['forced'] for x in (p,supervisor)) and not c['forced'] and c['within_deadline'] and c['completed_epoch']<=epoch+42180
    return {'stage':root.name,'closure_valid':bool(clean),'operational':bool(clean and p['returncode']==p['worker_returncode']==0),
        'returncode':p['returncode'],'worker_returncode':p['worker_returncode'],'coordinator_identity':launch['coordinator_identity'],
        'worker_identity':worker['worker_identity'],'supervisor_identity':launch['supervisor_identity'],'owned_identities':p['owned_identities'],
        'started_epoch':c['started_epoch'],'completed_epoch':c['completed_epoch'],'started_monotonic':c['started_monotonic'],'completed_monotonic':c['completed_monotonic'],
        'raw_files':{n:{'bytes':len(read(root/n)),'sha256':sha(read(root/n))} for n in ('closure.json','owned-tree/launch.json','owned-tree/worker-launch.json','owned-tree/supervisor-result.json','owned-tree/closure.json')}}


def verify_wrappers(launcher_root,*,expected_jit,notebook_release,reviewed_environment,runtime_outer_raw,runtime_owned_result_raw,runtime_terminal_raw):
    """Replay provider-downloaded wrapper tree against externally authenticated inputs.

    expected_jit is the pure finalizer's exact four-name dict[str, bytes].
    notebook_release and reviewed_environment must come from the sealed candidate.
    The three runtime byte inputs are exact provider-downloaded outer-closure,
    owned-result and external terminal documents, authenticated by the collector.
    No input here can itself grant production, model, provider or scoring authority.
    """
    root=Path(launcher_root);r=notebook_release
    mapping={'outer.ipynb':'active-finalized.ipynb','original-request.json':'original-request.json','operator.json':'operator.json','parent-private-scorer.json':'parent-private-scorer.json'}
    need(set(expected_jit)==set(mapping.values()),'exact expected JIT documents')
    for name,key in mapping.items():need(type(expected_jit[key]) is bytes and read(root/name)==expected_jit[key],'exact JIT '+name)
    owner=parse(expected_jit['original-request.json']);operator=parse(expected_jit['operator.json']);epoch=owner['original_epoch']
    prep=obj(root/'preparation-request.json');parent=obj(root/'installed-parent-request.json');receipt=obj(root/'preparation-receipt.json');result=obj(root/'result.json')
    closed(prep,{'format','ready','release','finalized','notebook_python_executable','output_root','input_root','epoch','launcher_root','environment_root'},'irisx/rlvr-parent-preparation-request-v1')
    closed(parent,{'format','source_root','output_root','config','paths','result_path','source_sha256'},'irisx/rlvr-installed-parent-request-v1')
    output='/kaggle/working/irisx-qwen14b-rlvr-20261012-run001';source='/kaggle/working/irisx-qwen14b-rlvr-20261012-source001/runtime';launcher=output+'-launcher';deployment=str(Path(source).parent/'deployment')
    need(prep['release']==r and prep['finalized']=={'owner_request':owner,'operator':operator},'reviewed release/JIT request binding')
    need(prep['epoch']==epoch and prep['output_root']==parent['output_root']==output and prep['input_root']=='/kaggle/input' and prep['launcher_root']==launcher and prep['environment_root']==ENV,'exact original preparation paths/epoch')
    ready=prep['ready'];need(ready['source_root']==source and parent['source_root']==source and parent['source_sha256']==ready['source_sha256']==r['source_sha256'],'complete source identity')
    need(ready['source_archive_path']==str(Path(source).parent/'source.zip') and ready['source_archive_sha256']==r['source_archive_sha256'] and ready['manifest_sha256']==r['code_manifest_sha256'],'source archive/manifest lineage')
    need(type(prep['notebook_python_executable']) is str and prep['notebook_python_executable'].startswith('/') and '..' not in Path(prep['notebook_python_executable']).parts,'observed notebook interpreter path')
    expected_paths={'outer_notebook_path':launcher+'/outer.ipynb','operator_path':launcher+'/operator.json','material_review_path':str(Path(source).parent/'release/MATERIAL-REVIEW.json'),'source_archive_path':ready['source_archive_path'],'original_request_path':launcher+'/original-request.json','parent_scorer_path':launcher+'/parent-private-scorer.json'}
    need(parent['paths']==expected_paths and parent['result_path']==launcher+'/result.json','exact parent-only file paths')
    config=parent['config'];need(set(config)=={'fixture','policy_path','environment_path','training_root','public_solver_root','model'} and config['fixture'] is False,'closed production parent config')
    need(config['model']==reviewed_environment['model_config'] and config['policy_path']==source+'/design/MEASURED-POLICY.json' and config['environment_path']==str(Path(source).parent/'release/REVIEWED-ENVIRONMENT.json'),'reviewed environment/policy model inputs')
    data='/kaggle/input/datasets/'+r['material_pins']['data']['reference'].rsplit('/',1)[0];training='/kaggle/input/datasets/'+r['material_pins']['training']['reference'].rsplit('/',1)[0]
    need(config['public_solver_root']==data+'/solver' and config['training_root']==training+'/data/training','solver-only and training roots')
    closed(receipt,{'format','source_sha256','source_acceptance','original_epoch','installed_offline','offline_environment','model_mount','public_answers_opened','model_loaded_by_preparation','storage_plan','disk_admission','actual_disk_free_bytes'},'irisx/rlvr-offline-preparation-receipt-v1')
    need(receipt['source_sha256']==r['source_sha256'] and receipt['source_acceptance']==ready and receipt['original_epoch']==epoch and receipt['installed_offline'] is True and receipt['public_answers_opened'] is False and receipt['model_loaded_by_preparation'] is False and receipt['model_mount']==config['model']['model_path'],'preparation material lineage')
    installed=receipt['offline_environment'];need(set(installed)=={'python_command','installed_offline','reused_environment','actual_environment_lock_path','actual_environment_lock_sha256','interpreter'} and installed['installed_offline'] is True and installed['reused_environment'] is False,'fresh installed environment receipt')
    command=[ENV+'/environment-cp312-cu128/bin/python','-I','-B','-S',ENV+'/environment-cp312-cu128/offline-run.py']
    need(installed['python_command']==command and installed['actual_environment_lock_path']==ENV+'/environment-cp312-cu128/evidence/environment-lock.json','source-derived installed interpreter command')
    raw=read(root/'interpreter-manifest.json');need(sha(raw)==INTERPRETER_MANIFEST,'exact interpreter manifest bytes')
    manifest=parse(raw);interpreter=installed['interpreter']
    need(interpreter=={'manifest_sha256':INTERPRETER_MANIFEST,'archive_sha256':INTERPRETER_ARCHIVE,'executable_sha256':manifest['members']['python/bin/python3.12']['sha256'],'verified_member_count':len(manifest['members'])},'complete installed interpreter identity')
    a=verify_stage(root/'preparation',expected_argv=[prep['notebook_python_executable'],'-I','-B',deployment+'/prepare_entry.py',launcher+'/preparation-request.json',sha(read(root/'preparation-request.json'))],epoch=epoch,scope='entire-owned-preparation-and-runtime')
    b=verify_stage(root/'installed-parent',expected_argv=command+[deployment+'/parent_entry.py',launcher+'/installed-parent-request.json',sha(read(root/'installed-parent-request.json'))],epoch=epoch,scope='installed-parent-with-owned-model-child')
    need(identity(b['coordinator_identity'])==identity(a['worker_identity']),'preparation to installed-parent coordinator incarnation')
    need(identities(b['owned_identities'])<=identities(a['owned_identities']),'complete nested owned-tree membership')
    for start,end in (('started_epoch','completed_epoch'),('started_monotonic','completed_monotonic')):need(a[start]<=b[start]<=b[end]<=a[end],'nested stage interval')
    for raw in (runtime_outer_raw,runtime_owned_result_raw,runtime_terminal_raw):need(type(raw) is bytes and 0<len(raw)<=16*1024**2,'bounded exact runtime documents')
    runtime_outer=parse(runtime_outer_raw);owned=parse(runtime_owned_result_raw);terminal=parse(runtime_terminal_raw)
    need(runtime_outer['schema']=='owned-parent-supervision-v1' and runtime_outer['fixture'] is False and runtime_outer['launch_source_sha256']==r['source_sha256'] and runtime_outer['output_root']==output,'actual runtime closure source')
    incarnation=runtime_outer['worker_incarnation'];need(runtime_outer['worker_pid'] not in {b['worker_identity']['pid'],b['supervisor_identity']['pid'],b['coordinator_identity']['pid']},'runtime worker is a distinct child');matches=[x for x in b['owned_identities'] if x['pid']==runtime_outer['worker_pid']]
    need(len(matches)==1 and incarnation is not None and matches[0]['birth']==incarnation['start_ticks'] and matches[0]['session']==incarnation['session_id']==incarnation['process_group']==runtime_outer['worker_pid'],'runtime model-worker incarnation/session belongs to installed-parent tree')
    need(finite(runtime_outer['started_monotonic']) and finite(runtime_outer['exit_observed_monotonic']) and b['started_monotonic']<=runtime_outer['started_monotonic']<=runtime_outer['exit_observed_monotonic']<=b['completed_monotonic'],'runtime supervision interval inside installed parent')
    need(runtime_outer['original_clock']['original_epoch']==epoch and owned['clock']==runtime_outer['original_clock']==terminal['original_clock'],'runtime original clock chain')
    need(owned['format']=='owned-rl-result-v1' and owned['fixture'] is False and owned['source_sha256']==terminal['source_sha256']==r['source_sha256'],'runtime result source/fixture')
    need(owned['outer_closure_ref']=={'path':output+'/outer-closure.json','file_sha256':sha(runtime_outer_raw)},'owned result raw outer closure binding')
    need(terminal['archive_complete'] is True and terminal['output_root']==output,'complete exported terminal document')
    for name,raw in (('outer-closure.json',runtime_outer_raw),('owned-result.json',runtime_owned_result_raw)):
        need(terminal['archive']['members'][name]=={'bytes':len(raw),'sha256':sha(raw)},'exact sealed runtime '+name)
    need({k:value for k,value in result.items() if k!='terminal_export'}==owned,'parent result exact owned-result projection')
    expected_terminal={**terminal,'terminal_receipt':{'path':output+'.evidence.zip.terminal.json','sha256':sha(runtime_terminal_raw),'bytes':len(runtime_terminal_raw)}}
    need(result['terminal_export']==expected_terminal,'parent result exact external terminal projection')
    success=result.get('status') in ('owned-mechanics-complete-PUBLIC-sealed','owned-mechanics-partial-comparison-PUBLIC-sealed') and result.get('terminal_export',{}).get('status')=='complete'
    need(not b['operational'] or success,'successful parent return requires complete owned result')
    return {'format':'irisx/rlvr-parent-wrapper-verification-v1','closure_valid':a['closure_valid'] and b['closure_valid'],
        'operational':a['operational'] and b['operational'] and success,'stages':[a,b],'original_epoch':epoch,'outer_deadline_epoch':epoch+42180,
        'source_sha256':r['source_sha256'],'runtime_tree_link_checked':True,
        'authority_scope':'externally hash-bound source and numeric-provider archived observations; trusted-code/same-UID boundary',
        'VM_teardown_or_billing_claim':False}
