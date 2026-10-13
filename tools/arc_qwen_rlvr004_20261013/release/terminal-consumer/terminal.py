"""Independent bounded terminal transport, preserving original inventory bytes."""
from pathlib import Path
import hashlib, os, shutil
from .consumer.safe_io import Root, need, same, is_sha, integer, finite, relative, parse_json
from .streaming_zip import (verify_evidence_zip, preflight_evidence_zip, _identity,
                            CHUNK_BYTES, DISK_RESERVE_BYTES, OVERHEAD_BYTES)

CAPS={'evidence_bytes':5*1024**3,'checkpoint_bytes':4*1024**3,'members':12000,
      'json_member_bytes':2*1024**3,'journal_bytes':8192*400000,
      'free_disk_reserve_bytes':4*1024**3,'archive_overhead_bytes':16*1024**2,
      'stream_chunk_bytes':1024**2}
LABELS=('base','A','B','C',*(f'B-batch-{i}' for i in range(4)))


def verify_terminal(archive_path, terminal_path, *, expected_archive_sha256,
                    expected_terminal_sha256, expected_source_sha256,
                    expected_inventory_sha256, expected_request_sha256,
                    expected_outer_sha256):
    """Expectations must be supplied by reviewed external collection, not receipt."""
    p=Path(terminal_path).absolute();troot=Root(p.parent)
    need(is_sha(expected_terminal_sha256) and troot.file_sha(p.name,16*1024**2)==expected_terminal_sha256,
         'authenticated terminal bytes differ')
    terminal=parse_json(troot.read(p.name,16*1024**2))
    need(terminal.get('format')=='owned-rl-evidence-terminal-v1' and terminal.get('archive_complete') is True
         and terminal.get('status') in ('complete','diagnostic'), 'completed terminal archive required')
    need(terminal.get('mode')=='runtime-reload-bound' and same(terminal.get('caps'),CAPS),
         'source-fixed streaming transport caps/mode differ')
    for key in ('scientific_goal_met','production_admitted','model_success_claim',
                'independent_checkpoint_tensor_verification','external_archive_sha256_independently_verified'):
        need(terminal.get(key) is False,'terminal cannot self-approve '+key)
    need(terminal.get('model_closed') is (terminal['status']=='complete'),'terminal closure classification differs')
    authorization=terminal.get('authorization',{})
    need(authorization.get('source_sha256')==expected_source_sha256
         and authorization.get('owner_request_ref',{}).get('file_sha256')==expected_request_sha256
         and authorization.get('outer_closure_ref',{}).get('file_sha256')==expected_outer_sha256,
         'terminal external source/request/outer lineage differs')
    need(authorization.get('worker_exited') is True and authorization.get('worker_session_empty') is True,
         'terminal requires actual owner process termination')
    need(authorization.get('kind')==('live-owned-model-closure' if terminal['model_closed'] else 'live-owned-process-termination'),
         'terminal authority class differs')
    need(finite(terminal.get('started_monotonic')) and finite(terminal.get('finished_monotonic'))
         and authorization['original_clock']['origin_monotonic']<=terminal['started_monotonic']<=terminal['finished_monotonic']
         and terminal['started_monotonic']<authorization['original_deadlines']['absolute']
         and terminal.get('terminal_metadata_may_finish_after_absolute_deadline') is True,'terminal original export interval differs')
    extra=terminal.get('retained_body_exceptions',{})
    allowed_exceptions={'checkpoints.zip'}|{f'experiment/checkpoints/{label}/{tail}' for label in LABELS for tail in ('state.pt','adapter/adapter_model.safetensors')}
    need(type(extra) is dict and set(extra)<=allowed_exceptions,'unsupported retained checkpoint exception')
    checkpoint_body=extra.get('checkpoints.zip')
    if checkpoint_body is not None:
        # The exporter describes this row as its original inventory row.
        need(terminal['status']=='diagnostic','successful compact terminal cannot retain checkpoint ZIP')
        checkpoint_body={'bytes':checkpoint_body['original_bytes'],'sha256':checkpoint_body['original_sha256']}
    actual=verify_evidence_zip(archive_path,checkpoint_archive_body=checkpoint_body)
    need(is_sha(expected_archive_sha256) and actual['sha256']==expected_archive_sha256,'authenticated actual archive bytes differ')
    declared=terminal.get('archive',{})
    need(set(declared)==set(actual) and same({k:v for k,v in declared.items() if k!='path'},
                                          {k:v for k,v in actual.items() if k!='path'}),
         'terminal streamed CRC/SHA inventory differs from received bytes')
    need(terminal.get('original_artifact_inventory')==actual['members'].get('artifact-inventory.json')
         and actual['members']['artifact-inventory.json']['sha256']==expected_inventory_sha256,
         'original inventory bytes not retained/authenticated')
    need(actual['members'].get('owner-request.json',{}).get('sha256')==expected_request_sha256
         and actual['members'].get('outer-closure.json',{}).get('sha256')==expected_outer_sha256,
         'received owner/outer bytes differ from terminal authority')
    return terminal,actual


def materialize_archive(archive_path, destination, *, verified, checkpoint_archive_body=None):
    """Streaming copy into fresh local root; no extraction parser or tensor load."""
    destination=Path(destination).absolute()
    need(not destination.exists() and destination.parent.is_dir(),'fresh materialization directory required')
    need(all(not p.is_symlink() for p in (destination,*destination.parents)), 'regular materialization ancestry')
    pre=preflight_evidence_zip(archive_path,checkpoint_archive_body=checkpoint_archive_body)
    need(pre['bytes']==verified['bytes'] and pre['uncompressed_bytes']==verified['uncompressed_bytes'],
         'archive changed before materialization')
    need(shutil.disk_usage(destination.parent).free>=pre['uncompressed_bytes']+OVERHEAD_BYTES+DISK_RESERVE_BYTES,
         'actual materialization bytes plus4GiB reserve required')
    destination.mkdir(mode=0o700)
    with Path(archive_path).open('rb') as incoming:
        need(_identity(os.fstat(incoming.fileno()))==pre['file_identity'],'archive identity changed')
        for row in pre['members']:
            target=destination.joinpath(*relative(row['name']).parts);target.parent.mkdir(parents=True,exist_ok=True)
            incoming.seek(row['data_offset']);remaining=row['bytes'];h=hashlib.sha256()
            with target.open('xb') as outgoing:
                while remaining:
                    block=incoming.read(min(CHUNK_BYTES,remaining));need(block,'truncated archive copy')
                    remaining-=len(block);h.update(block);outgoing.write(block)
            need({'bytes':target.stat().st_size,'sha256':h.hexdigest()}==verified['members'][row['name']],
                 'actual materialized bytes differ: '+row['name'])
        need(_identity(os.fstat(incoming.fileno()))==pre['file_identity']==_identity(Path(archive_path).stat()),
             'archive changed during materialization')
    return destination


def check_external_bodies(root,terminal,verified):
    inv=root.json('artifact-inventory.json');files=inv['files'];members=verified['members']
    missing=set(files)-set(members);external=terminal.get('external_bodies')
    need(type(external) is dict and set(external)==missing and set(members)-set(files)=={'artifact-inventory.json'},
         'precise compact archive omissions differ')
    allowed={'checkpoints.zip'}
    for label in LABELS:
        manifest_name=f'experiment/checkpoints/{label}/manifest.json'
        if manifest_name not in files:continue
        manifest=root.json(manifest_name)
        for tail in ('state.pt','adapter/adapter_model.safetensors'):
            name=f'experiment/checkpoints/{label}/{tail}'
            need(name in files and manifest.get('files',{}).get(tail)==files[name]['sha256'],
                 'omission candidate missing manifest binding')
            allowed.add(name)
    need(missing<=allowed,'non-tensor evidence cannot be omitted')
    for name,row in external.items():
        need(row.get('original_sha256')==files[name]['sha256'] and row.get('original_bytes')==files[name]['bytes'],
             'external body original hash/length differs')
        need(row.get('local_presence_observed') is True and row.get('local_sha256_verified') is True
             and row.get('local_observed_sha256')==files[name]['sha256'] and row.get('local_observed_bytes')==files[name]['bytes'],
             'source-local external body verification differs')
        need(row.get('archive_body_included') is False and row.get('external_body_materialized') is False
             and row.get('external_sha256_independently_verified') is False and row.get('external_observed_sha256') is None,
             'unreceived external tensor bytes cannot become independently verified')
    return {'external_bodies':sorted(missing),'independent_checkpoint_tensor_verification':False}
