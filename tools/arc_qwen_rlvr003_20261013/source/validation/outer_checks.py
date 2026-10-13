"""Parent-envelope content replay, separate from live capability authority."""
from pathlib import Path
from .safe_io import Root,need,same,is_sha,integer,finite,digest
from .ledger_checks import validate_clock,replay_journal,resolved_events,OFFSETS
from .prediction_checks import reference


def artifact_inventory(root,expected_sha256=None,*,checkpoint_mode="full-materialized",checkpoint_archive_observation=None):
    value=root.json('artifact-inventory.json')
    if expected_sha256 is not None:
        need(is_sha(expected_sha256) and root.file_sha('artifact-inventory.json')==expected_sha256,'independently pinned artifact inventory differs')
    need(value.get('format')=='owned-rl-artifact-inventory-v1' and value.get('exclusions')==['artifact-inventory.json'] and value.get('truncated') is False,'full untruncated owned artifact inventory required')
    actual=root.inventory();actual.pop('artifact-inventory.json');files=value.get('files')
    need(checkpoint_mode in ('full-materialized','runtime-reload-bound'),'explicit checkpoint verification mode')
    allowed={f'experiment/checkpoints/{label}/{name}' for label in ('base','A','B','C') for name in ('state.pt','adapter/adapter_model.safetensors','adapter/README.md')} if checkpoint_mode=='runtime-reload-bound' else set()
    need(type(files) is dict and files,'complete artifact inventory required')
    if checkpoint_mode=='runtime-reload-bound' and 'checkpoints.zip' in files:allowed.add('checkpoints.zip')
    missing=set(files)-set(actual)
    need(type(files) is dict and set(actual)<=set(files) and missing<=allowed,'full archived artifact inventory missing/extra required members')
    if missing:
        obs=checkpoint_archive_observation
        need(type(obs) is dict and obs.get('filename')=='checkpoints.zip' and obs.get('present') is True and integer(obs.get('byte_length'),1,3*1024**3+2*1024**2),'unmaterialized checkpoint ZIP presence/size observation required')
        need(obs.get('transport_observation') in ('HTTP200_CONTENT_LENGTH_VERIFIED','DECLARED_LOCAL_ARCHIVE_PRESENT') and obs.get('body_materialized') is False and obs.get('independently_sha256_verified') is False and obs.get('observed_sha256') is None,'checkpoint observation must not imply unperformed byte/hash verification')
    evidence=checkpoints=0
    for name,entry in files.items():
        need(type(entry) is dict and set(entry)=={'bytes','sha256'} and integer(entry['bytes'],0,max(3*1024**3,8192*400000)) and is_sha(entry['sha256']) and (name in missing or entry['bytes']==root.member(name).stat().st_size and entry['sha256']==actual[name]),'archived artifact length/hash differs: '+name)
        if name=='checkpoints.zip':need(entry['bytes']<=3*1024**3,'checkpoint ZIP cap')
        elif name.startswith('experiment/checkpoints/'):
            checkpoints+=entry['bytes'];need(entry['bytes']<=768*1024**2,'checkpoint individual cap')
        else:
            evidence+=entry['bytes'];need(entry['bytes']<=(8192*400000 if name=='physical-journal.jsonl' else 2*1024**3),'evidence individual cap')
    need(evidence<=8*1024**3 and checkpoints<=3*1024**3 and len(files)<=12000,'full archive evidence expansion cap')
    need(value.get('evidence_bytes')==evidence and value.get('checkpoint_bytes')==checkpoints,'artifact expansion totals differ')
    need(same(value.get('caps'),{'evidence_bytes':8*1024**3,'checkpoint_bytes':3*1024**3,'members':12000,'largest_json_member_bytes':2*1024**3,'disk_reserve_bytes':4*1024**3}),'source-fixed expansion caps differ')
    archive_verified=False
    if 'checkpoints.zip' in files:
        desc=root.json('checkpoint-zip-descriptor.json');owned=root.json('owned-result.json')
        need(same(desc,owned.get('checkpoint_export')) and desc.get('format')=='owned-checkpoint-zip-descriptor-v1','actual owned ZIP descriptor linkage')
        need(desc.get('bytes')==files['checkpoints.zip']['bytes'] and desc.get('sha256')==files['checkpoints.zip']['sha256'] and desc.get('runtime_export_verified') is True and desc.get('external_tensor_bytes_independently_downloaded') is False,'actual runtime ZIP inventory differs')
        store={n.removeprefix('experiment/checkpoints/'):v for n,v in files.items() if n.startswith('experiment/checkpoints/')}
        need(desc.get('members')==len(store) and desc.get('uncompressed_bytes')==checkpoints and same(desc.get('checkpoint_store_inventory'),{'files':store,'bytes':checkpoints,'cap_bytes':3*1024**3,'frozen_base_included':False}),'ZIP complete checkpoint store inventory differs')
        if 'checkpoints.zip' in missing:need(checkpoint_archive_observation['byte_length']==desc['bytes'],'observed ZIP length differs from source-owned descriptor')
        else:
            from .safe_io import inspect_tensor_zip,sha
            import zipfile
            path=root.member('checkpoints.zip');inspect_tensor_zip(path,maximum_bytes=3*1024**3,maximum_members=128)
            with zipfile.ZipFile(path) as z:
                need(set(z.namelist())==set(store),'actual checkpoint ZIP member inventory differs')
                for n,entry in store.items():
                    h=__import__('hashlib').sha256()
                    with z.open(n) as f:
                        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
                    need(z.getinfo(n).file_size==entry['bytes'] and h.hexdigest()==entry['sha256'],'actual checkpoint ZIP member bytes differ')
            archive_verified=True
    return {'files':len(files),'evidence_bytes':evidence,'checkpoint_bytes':checkpoints,'inventory_sha256':root.file_sha('artifact-inventory.json'),'externally_pinned':expected_sha256 is not None,'unmaterialized_checkpoint_assets':sorted(missing),'checkpoint_archive_observation':checkpoint_archive_observation,'independent_archive_body_hash_verification':archive_verified}


def parent_envelope(root,*,expected_source_sha256,journal_auth_key=None):
    owned=root.json('owned-result.json');request=root.json('owner-request.json');clock=root.json('owner-clock.json');outer=root.json('outer-closure.json');inner=root.json('inner-closure.json');source=root.json('release-source-inventory.json')
    need(owned.get('format')=='owned-rl-result-v1' and request.get('format')=='owned-rl-worker-request-v1','owned parent/request format')
    need(owned.get('fixture') is request.get('config',{}).get('fixture') is clock.get('fixture') and type(owned.get('fixture')) is bool,'owner fixture scope changed')
    need(same(owned.get('clock'),clock) and same(request.get('clock'),clock) and same(outer.get('original_clock'),clock) and same(inner.get('clock'),clock),'original owner clock differs between phases')
    origin=validate_clock(clock)
    need(same(outer.get('original_deadlines'),{k:origin+v for k,v in OFFSETS.items()}),'outer reset/extended original clock')
    need(source.get('source_sha256')==owned.get('source_sha256')==expected_source_sha256 and digest(sorted(source.get('files',{}).items()))==expected_source_sha256 and same(request.get('sources'),source['files']),'owner/source complete release inventory differs')
    need(request.get('plan_sha256')==owned.get('plan_sha256')==inner.get('plan_sha256'),'owner/inner frozen plan changed')
    request_sha=root.file_sha('owner-request.json')
    need(inner.get('request_sha256')==outer.get('request_sha256')==request_sha,'owner request byte binding differs')
    need(inner.get('format')=='owned-rl-inner-closure-v1' and outer.get('schema')=='owned-parent-supervision-v1','owned closure schema')
    need(outer.get('inner_closure_sha256')==root.file_sha('inner-closure.json') and same(outer.get('inner_closure'),inner),'outer inner-closure byte/object linkage')
    need(same(reference(root,owned['outer_closure_ref'],request['output_root']),outer),'owned result outer closure alias')
    need(inner.get('public_gold_opened') is False,'model owner crossed PUBLIC gold boundary')
    journal=replay_journal(root,clock=clock,key=journal_auth_key)
    for key in ('journal_id','head_sha256','record_count','event_count','closed','settled','unknown_operation_ids','cost_charges'):
        need(same(outer.get('journal',{}).get(key),journal[key]),'outer durable journal summary differs: '+key)
    need(same(resolved_events(root,outer['journal'],request['output_root']),journal['physical_events']),'outer durable final stream differs from full journal replay')
    binding=[r for r in journal['artifact_bindings'] if r.get('label')=='inner-closure']
    need(len(binding)==1 and binding[0].get('sha256')==root.file_sha('inner-closure.json') and root.remap(binding[0].get('path'),request['output_root'])=='inner-closure.json','durable owner closure artifact linkage missing')
    need(type(outer.get('worker_exited')) is bool and type(outer.get('safe_closure')) is bool,'explicit outer lifecycle status')
    need(integer(outer.get('worker_pid'),1) and finite(outer.get('started_monotonic')) and finite(outer.get('exit_observed_monotonic')) and outer['started_monotonic']<=outer['exit_observed_monotonic'],'outer process incarnation/observed time required')
    incarnation=outer.get('worker_incarnation')
    need(type(incarnation) is dict and incarnation.get('pid')==outer['worker_pid'] and integer(incarnation.get('start_ticks'),1),'actual worker process incarnation required')
    need(type(outer.get('worker_session_members')) is list and outer.get('worker_session_empty') is (not outer['worker_session_members']),'owned descendant/session exit projection')
    argv=outer.get('worker_argv');need(type(argv) is list and len(argv)>=6 and str(argv[-4]).endswith('/owned_runtime/worker.py') and argv[-2]==request_sha,'outer executed worker/request differs')
    need(root.remap(argv[-3],request['output_root'])=='owner-request.json','outer launched different owner request')
    safe=(outer['worker_exited'] and type(outer.get('worker_returncode')) is int and outer['worker_returncode']==0 and outer['worker_session_empty'] and outer.get('hard_stop') is None and outer.get('integrity_error') is None and outer.get('closure_error') is None and journal['settled'] and outer['exit_observed_monotonic']<origin+42180)
    closure=inner.get('model_closure')
    safe &= type(closure) is dict and all(closure.get(k) is True for k in ('closed','future_operations_blocked','model_references_released','device_synchronized','model_stopped','ledger_settled')) and closure.get('fatal_native_state') is None
    need(outer['safe_closure'] is bool(safe) and outer.get('model_stopped') is bool(safe),'outer closure not derived from owned process/device/ledger evidence')
    if safe:
        need(journal['physical_events'] and journal['physical_events'][0]['started']<=outer['started_monotonic']+1800.,'actual pre-first-operation startup exceeded hard cap')
        need(inner.get('status')=='complete' and inner.get('error') is None,'failed inner work promoted as complete')
        need(any(e['phase']=='session-cleanup' and e['dispatched'] and e['status']=='complete' for e in journal['physical_events']),'actual durable cleanup absent')
        for e in journal['physical_events']:
            need(outer['started_monotonic']-.01<=e['started']<=e['ended']<=outer['exit_observed_monotonic']+.001,'physical work outside parent process lifetime')
            need(e['ended']<=e['hard_deadline']+.001,'completed operation exceeded supervised hard cap')
    return {'owned':owned,'request':request,'clock':clock,'outer':outer,'inner':inner,'source':source,'journal':journal,'safe_closure':bool(safe),'original_root':request['output_root']}
