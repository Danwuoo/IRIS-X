"""Explicit expansion caps; complete streams retained once, never silently truncated."""
from pathlib import Path
import shutil, stat
from .release import need,file_sha
EVIDENCE_CAP_BYTES=5*1024**3
CHECKPOINT_CAP_BYTES=4*1024**3
MAX_MEMBERS=12000
MAX_JSON_MEMBER_BYTES=2*1024**3
DISK_RESERVE_BYTES=4*1024**3

def seal_artifact_inventory(root):
    from experiment_flow.contracts import write_json
    root=Path(root).resolve();files={};evidence=checkpoints=0
    for p in sorted(root.rglob('*')):
        need(not p.is_symlink(),'artifact symlink forbidden')
        if p.is_dir():continue
        need(stat.S_ISREG(p.lstat().st_mode),'nonregular artifact forbidden')
        name=p.relative_to(root).as_posix();size=p.stat().st_size
        need(name!='artifact-inventory.json','artifact inventory already sealed')
        is_checkpoint=name.startswith('experiment/checkpoints/')
        if is_checkpoint:checkpoints+=size
        elif name!='checkpoints.zip':evidence+=size
        limit=(768*1024**2 if is_checkpoint else CHECKPOINT_CAP_BYTES if name=='checkpoints.zip' else
               MAX_JOURNAL_BYTES if name=='physical-journal.jsonl' else MAX_JSON_MEMBER_BYTES)
        need(size<=limit,'artifact member cap')
        files[name]={'bytes':size,'sha256':file_sha(p)}
    need(len(files)<=MAX_MEMBERS and evidence<=EVIDENCE_CAP_BYTES and checkpoints<=CHECKPOINT_CAP_BYTES,'complete artifact expansion caps')
    return write_json(root/'artifact-inventory.json',{'format':'owned-rl-artifact-inventory-v1','files':files,
        'evidence_bytes':evidence,'checkpoint_bytes':checkpoints,'exclusions':['artifact-inventory.json'],
        'caps':{'evidence_bytes':EVIDENCE_CAP_BYTES,'checkpoint_bytes':CHECKPOINT_CAP_BYTES,'members':MAX_MEMBERS,
                'largest_json_member_bytes':MAX_JSON_MEMBER_BYTES,'disk_reserve_bytes':DISK_RESERVE_BYTES},
        'audit_streams':'original trajectories occur once in audit/sweep-N.json; result contains hash references',
        'physical_stream':'one generation parent owns each dense token-forward sequence; no per-token journal fsync',
        'truncated':False})

# Derived ceilings of this exact source protocol, not inherited ZIP guesses.
MAX_TOKEN_STEP_BYTES=1024
MAX_TRAJECTORY_METADATA_BYTES=256*1024
MAX_REPLAY_BYTES=64*1024
MAX_EVENT_BYTES=8192
MAX_EVENT_COUNT=40000
MAX_JOURNAL_RECORDS=400000
MAX_JOURNAL_BYTES=MAX_EVENT_BYTES*MAX_JOURNAL_RECORDS
_OWNED_OUTPUTS=set()
_EXPORT_CACHE={}

def expansion_plan():
    import json
    from . import ROOT
    tokenizer=ROOT/'baseline/materials/qwen14b/hf-overlay/tokenizer.json'
    raw=json.loads(tokenizer.read_text());added={r['id'] for r in raw['added_tokens']}
    pieces={i:t for t,i in raw['model']['vocab'].items() if t and all(c in '0123456789\u010a' for c in t) and i not in added}
    need(len(pieces)==25,'source-pinned tokenizer alphabet changed')
    trajectories=4*8*8;steps=1024
    audits=trajectories*(steps*MAX_TOKEN_STEP_BYTES+MAX_TRAJECTORY_METADATA_BYTES+2*MAX_REPLAY_BYTES)
    # SFT forward/backward+commit; rollout/replay/backward; paired+PUBLIC;
    # additional source-bounded restore/save/reload/setup/cleanup reserve.
    operations=(256+8192)*4+trajectories*4+288+334+128
    journal=MAX_EVENT_BYTES*MAX_JOURNAL_RECORDS
    projections=2*MAX_EVENT_BYTES*MAX_EVENT_COUNT
    # All prediction text/token/prompt+calibration+source/escrow metadata.
    remaining=512*1024**2
    bound=audits+journal+projections+remaining
    need(operations<MAX_EVENT_COUNT and bound<=EVIDENCE_CAP_BYTES,'derived evidence budget does not fit source cap')
    return {'format':'owned-rl-evidence-expansion-v1','tokenizer_sha256':file_sha(tokenizer),
        'grid_ascii_pieces':25,'EOS_choices':2,'maximum_step_support':27,'trajectories':trajectories,
        'max_steps_per_trajectory':steps,'enforced_step_bytes':MAX_TOKEN_STEP_BYTES,
        'enforced_trajectory_metadata_bytes':MAX_TRAJECTORY_METADATA_BYTES,'per_replay_allowance_bytes':MAX_REPLAY_BYTES,'replay_projection_copies':2,
        'audit_upper_bytes':audits,'max_source_model_operations':operations,'enforced_event_count_cap':MAX_EVENT_COUNT,
        'enforced_journal_record_bytes':MAX_EVENT_BYTES,'enforced_journal_record_count':MAX_JOURNAL_RECORDS,
        'journal_upper_bytes':journal,'event_projection_copies_bound':2,'event_projection_upper_bytes':projections,
        'predictions_calibration_metadata_allowance_bytes':remaining,'derived_evidence_upper_bytes':bound,
        'evidence_cap_bytes':EVIDENCE_CAP_BYTES,'single_json_cap_bytes':MAX_JSON_MEMBER_BYTES,
        'largest_planned_audit_json_upper_bytes':audits//4,
        'checkpoint_cap_bytes':CHECKPOINT_CAP_BYTES,'checkpoint_temporary_ZIP_cap_bytes':CHECKPOINT_CAP_BYTES,
        'optional_full_export_ZIP_cap_bytes':EVIDENCE_CAP_BYTES+2*CHECKPOINT_CAP_BYTES+16*1024**2,
        'optional_full_export_contains_checkpoint_store_and_zip':True,
        'free_disk_reserve_bytes':DISK_RESERVE_BYTES,'unknown_work_retained':True,'silent_truncation':False}

def register_output(root):
    root=Path(root).resolve();need(root.is_dir(),'acquired output directory required')
    _OWNED_OUTPUTS.add(root)

def admit_write(path,byte_count):
    need(type(byte_count) is int and 0<=byte_count<=MAX_JSON_MEMBER_BYTES,'bounded complete artifact write')
    path=Path(path).absolute()
    owned=next((r for r in _OWNED_OUTPUTS if path.resolve().is_relative_to(r)),None)
    if owned is None:return # old controlled fixtures have no owned runtime scope
    need(not any(p.is_symlink() for p in (path,*path.parents)),'output symlink before write')
    members=evidence=checkpoint=metadata=0
    for p in owned.rglob('*'):
        need(not p.is_symlink(),'owned output symlink')
        if p.is_dir():continue
        need(stat.S_ISREG(p.lstat().st_mode),'nonregular artifact forbidden')
        members+=1;n=p.relative_to(owned).as_posix()
        if n.startswith('experiment/checkpoints/'):checkpoint+=p.stat().st_size
        elif n!='checkpoints.zip':
            evidence+=p.stat().st_size
            if not n.startswith('experiment/audit/') and 'physical-events' not in p.name and not n.startswith('physical-journal.jsonl'):metadata+=p.stat().st_size
    proposed=path.resolve().relative_to(owned).as_posix()
    if not proposed.startswith('experiment/audit/') and 'physical-events' not in path.name and not proposed.startswith('physical-journal.jsonl'):metadata+=byte_count
    need(metadata<=512*1024**2,'aggregate non-audit/journal/event/checkpoint evidence cap')
    need(members<MAX_MEMBERS and evidence+byte_count<=EVIDENCE_CAP_BYTES and checkpoint<=CHECKPOINT_CAP_BYTES,'prewrite complete evidence expansion bound')
    need(shutil.disk_usage(owned).free>=byte_count+DISK_RESERVE_BYTES+future_export_reserve_for(path,byte_count,refresh=True),
         'artifact write preserves4GiB free disk and outstanding complete exports')

def admit_journal_append(path,byte_count,sequence):
    need(byte_count<=MAX_EVENT_BYTES and sequence<MAX_JOURNAL_RECORDS,'journal record expansion bound')
    p=Path(path);current=p.stat().st_size if p.exists() else 0
    need(current+byte_count<=MAX_JOURNAL_BYTES,'complete journal expansion cap')
    need(shutil.disk_usage(p.parent).free>=byte_count+DISK_RESERVE_BYTES+future_export_reserve_for(p,byte_count),
         'journal append preserves4GiB free disk and outstanding complete exports')

def export_owned_artifacts(capability,root,destination):
    """Optional local export, only after actual owned closure; no upload/launch."""
    import zipfile,time
    from .supervisor import verify_closed_capability
    from .storage import before_export
    closed=verify_closed_capability(capability)
    raw_root=Path(root).absolute();raw_destination=Path(destination).absolute()
    need(all(not p.is_symlink() for p in (raw_root,*raw_root.parents,raw_destination,*raw_destination.parents)),'regular archive ancestry')
    root=raw_root.resolve();destination=raw_destination.resolve()
    need(root==Path(closed['output_root']) and not destination.exists() and not destination.is_relative_to(root),'new external archive destination for same closed owner')
    before_export(root/'experiment/checkpoints')
    import json
    sealed=json.loads((root/'artifact-inventory.json').read_text())['files']
    files=[]
    for p in root.rglob('*'):
        need(not p.is_symlink(),'archive symlink denied')
        if p.is_dir():continue
        need(stat.S_ISREG(p.lstat().st_mode),'regular archive members only')
        files.append(p)
    actual={p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':file_sha(p)} for p in files if p.name!='artifact-inventory.json'}
    need(actual==sealed,'complete artifact inventory differs before export')
    total=sum(p.stat().st_size for p in files)
    need(total<=EVIDENCE_CAP_BYTES+2*CHECKPOINT_CAP_BYTES and len(files)<=MAX_MEMBERS,'complete archive input expansion bound')
    need(shutil.disk_usage(destination.parent).free>=total+16*1024**2+DISK_RESERVE_BYTES,'temporary ZIP requires actual input bytes plus overhead and4GiB reserve')
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
        for p in sorted(files):
            need(time.monotonic()<closed['original_deadlines']['absolute'],'original absolute export deadline')
            need(not p.is_symlink(),'archive symlink denied')
            expected=file_sha(p);archive.write(p,p.relative_to(root).as_posix())
            need(file_sha(p)==expected,'archive source changed while streaming')
    need(destination.stat().st_size<=total+16*1024**2,'ZIP observed overhead exceeded allowance')
    verify_closed_capability(capability)
    return {'path':str(destination),'sha256':file_sha(destination),'bytes':destination.stat().st_size,'members':len(files)}


def pending_export_space(root):
    """Outstanding duplication of already-created bytes, independent of caps."""
    root=Path(root).resolve();checkpoint=evidence=compact=0
    for p in root.rglob('*'):
        need(not p.is_symlink(),'owned pending-export symlink')
        if not p.is_file():continue
        name=p.relative_to(root).as_posix();size=p.stat().st_size
        if name=='checkpoints.zip':continue
        if name.startswith('experiment/checkpoints/'):
            checkpoint+=size
            if p.name not in ('state.pt','adapter_model.safetensors'):compact+=size
        else:evidence+=size
    checkpoint_pending=0 if (root/'checkpoints.zip').is_file() else checkpoint
    terminal=root.with_name(root.name+'.evidence.zip')
    terminal_pending=0 if terminal.is_file() else evidence+compact
    overhead=(int(checkpoint_pending>0)+int(not terminal.is_file()))*16*1024**2
    return {'checkpoint_archive_pending_bytes':checkpoint_pending,'evidence_archive_pending_bytes':terminal_pending,
            'overhead_pending_bytes':overhead,'total_pending_bytes':checkpoint_pending+terminal_pending+overhead}


def future_export_reserve_for(path,extra_bytes,*,checkpoint=False,refresh=False,extra_compact_bytes=0):
    path=Path(path).resolve()
    owned=next((r for r in _OWNED_OUTPUTS if path.is_relative_to(r)),None)
    if owned is None:return 0
    # Model-operation journal appends change only the two known journal files.
    # Metadata/checkpoint admission refreshes the complete bounded file census.
    journal_paths=[owned/'physical-journal.jsonl',owned/'physical-journal.jsonl.anchor']
    current=sum(p.stat().st_size for p in journal_paths if p.is_file())
    if refresh or checkpoint or owned not in _EXPORT_CACHE:
        _EXPORT_CACHE[owned]={'pending':pending_export_space(owned)['total_pending_bytes'],'journal_bytes':current}
    cached=_EXPORT_CACHE[owned]
    pending=cached['pending']+max(0,current-cached['journal_bytes'])
    # Compact checkpoint metadata survives in BOTH the checkpoint and evidence
    # archives. Tensor bodies have only the checkpoint-archive copy.
    relative=path.relative_to(owned).as_posix()
    compact=(relative.startswith('experiment/checkpoints/') and not checkpoint and
             path.name not in ('state.pt','adapter_model.safetensors'))
    return pending+extra_bytes*(2 if compact else 1)+extra_compact_bytes
