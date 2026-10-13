"""Analytical new-format PEFT storage and actual bounded checkpoint inspection."""
from pathlib import Path
import json, shutil, stat
from . import ROOT
from .release import need,file_sha
GiB=1024**3
CHECKPOINT_STORE_CAP=4*GiB
MAX_CHECKPOINTS=7
DISK_RESERVE=4*GiB
METADATA_ALLOWANCE=32*1024**2

def storage_plan():
    path=ROOT/'baseline/materials/qwen14b/hf-overlay/config.json'
    c=json.loads(path.read_text());r=8;h=c['hidden_size'];k=c['num_key_value_heads']*c['head_dim'];q=c['num_attention_heads']*c['head_dim'];i=c['intermediate_size'];layers=c['num_hidden_layers']
    per_layer=r*((h+q)+(h+k)+(h+k)+(q+h)+3*(h+i))
    parameters=layers*per_layer;fp32=parameters*4
    # base plus A, four durable B batch boundaries, and C.
    # state.pt duplicates adapter; trained states include two Adam moments.
    payload=2*fp32+(MAX_CHECKPOINTS-1)*(4*fp32)
    estimate=payload+MAX_CHECKPOINTS*METADATA_ALLOWANCE
    need(estimate<CHECKPOINT_STORE_CAP,'analytical complete store exceeds source cap')
    return {'format':'owned-rl-checkpoint-storage-v2','maximum_checkpoint_count':MAX_CHECKPOINTS,'config_sha256':file_sha(path),'rank':r,
        'seven_projection_layers':layers,'lora_parameter_count':parameters,'parameter_dtype':'float32',
        'adapter_tensor_bytes':fp32,'base_payload_bytes':2*fp32,'trained_payload_bytes':4*fp32,
        'worst_case_checkpoint_tensor_bytes':payload,'metadata_allowance_bytes':MAX_CHECKPOINTS*METADATA_ALLOWANCE,
        'estimated_checkpoint_upper_bytes':estimate,'checkpoint_store_cap_bytes':CHECKPOINT_STORE_CAP,
        'zip_temporary_cap_bytes':CHECKPOINT_STORE_CAP,'free_disk_reserve_bytes':DISK_RESERVE,
        'full_store_plus_temporary_zip_plus_reserve_bytes':2*CHECKPOINT_STORE_CAP+DISK_RESERVE,
        'optimizer_moments':'two FP32 Adam tensors per adapter parameter; step scalars inside metadata allowance',
        'not_included':'frozen14B native weights remain external; never checkpoint-copied'}

def inspect_store(root):
    root=Path(root);files={};total=0
    if root.exists():
        for p in root.rglob('*'):
            need(not p.is_symlink(),'checkpoint symlink forbidden')
            if p.is_dir():continue
            need(stat.S_ISREG(p.lstat().st_mode),'nonregular checkpoint member forbidden')
            size=p.stat().st_size;name=p.relative_to(root).as_posix()
            limit=768*1024**2 if p.name=='state.pt' else 256*1024**2 if p.suffix=='.safetensors' else 16*1024**2
            need(size<=limit,'checkpoint file exceeds reviewed analytical limit')
            files[name]={'bytes':size,'sha256':file_sha(p)};total+=size
    need(total<=CHECKPOINT_STORE_CAP and len(files)<=128,'bounded complete checkpoint store')
    need(sum(name.endswith('/manifest.json') for name in files)<=MAX_CHECKPOINTS,'bounded checkpoint count')
    return {'files':files,'bytes':total,'cap_bytes':CHECKPOINT_STORE_CAP,'frozen_base_included':False}

def before_save(directory, *, fixture):
    directory=Path(directory);parent=directory.parent
    parent.mkdir(parents=True,exist_ok=True)
    inventory=inspect_store(parent);current=inventory['bytes']
    need(sum(name.endswith('/manifest.json') for name in inventory['files'])<MAX_CHECKPOINTS,'new checkpoint would exceed seven-checkpoint source bound')
    estimate=16*1024**2 if fixture else storage_plan()['trained_payload_bytes']+METADATA_ALLOWANCE
    need(current+estimate<=CHECKPOINT_STORE_CAP,'new checkpoint would exceed source bound')
    from .evidence import future_export_reserve_for
    need(shutil.disk_usage(parent).free>=estimate+DISK_RESERVE+future_export_reserve_for(directory,estimate,checkpoint=True,extra_compact_bytes=METADATA_ALLOWANCE),
         'checkpoint save requires4GiB reserve and complete outstanding exports')


def before_export(root):
    actual=inspect_store(root)
    need(actual['bytes']+16*1024**2<=CHECKPOINT_STORE_CAP,'ZIP overhead must fit inside4GiB cap')
    need(shutil.disk_usage(root).free>=actual['bytes']+16*1024**2+DISK_RESERVE,'temporary export ZIP requires actual bytes plus overhead plus4GiB reserve')
    return actual


def summarize_state(payload,adapter_sha256,parameter_names):
    """Exact tensor+primitive fingerprint projection, generated from owned state."""
    import torch,hashlib
    from tools.arc_next_models import digest
    def project(item):
        if torch.is_tensor(item):
            value=item.detach().cpu().contiguous()
            return {'tensor':True,'dtype':str(value.dtype),'shape':list(value.shape),
                    'sha256':hashlib.sha256(value.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()}
        if isinstance(item,dict):return {str(k):project(v) for k,v in sorted(item.items(),key=lambda pair:str(pair[0]))}
        if isinstance(item,(list,tuple)):return [project(v) for v in item]
        need(item is None or type(item) in (str,bool,int,float),'primitive owned state required')
        return item
    tree=project(payload)
    return {'format':'owned-rl-state-summary-v1','state_sha256':digest(tree),'adapter_sha256':adapter_sha256,
            'state_tree':tree,'optimizer_parameter_names':list(parameter_names),
            'optimizer_step_values':{str(k):float(v['step'].item()) for k,v in payload['optimizer']['state'].items()},
            'cleared_gradients':True}


def export_checkpoint_zip(capability,root,destination):
    import zipfile,time
    from .supervisor import verify_closed_capability
    closed=verify_closed_capability(capability)
    root=Path(root).resolve();destination=Path(destination).resolve()
    need(root==Path(closed['output_root'])/'experiment/checkpoints','same owned complete checkpoint store')
    need(not destination.exists() and destination==Path(closed['output_root'])/'checkpoints.zip','fresh owned checkpoint archive')
    inventory=before_export(root)
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
        for name,row in inventory['files'].items():
            need(time.monotonic()<closed['original_deadlines']['absolute'],'original checkpoint export deadline')
            path=root/name;need(file_sha(path)==row['sha256'],'checkpoint changed before export')
            archive.write(path,name);need(file_sha(path)==row['sha256'],'checkpoint changed while exporting')
    need(destination.stat().st_size<=CHECKPOINT_STORE_CAP,'checkpoint ZIP observed size cap')
    verify_closed_capability(capability)
    return {'format':'owned-checkpoint-zip-descriptor-v1','path':str(destination),'bytes':destination.stat().st_size,
            'sha256':file_sha(destination),'members':len(inventory['files']),'uncompressed_bytes':inventory['bytes'],
            'runtime_export_verified':True,'external_tensor_bytes_independently_downloaded':False,
            'checkpoint_store_inventory':inventory}


def before_session(root,*,fixture):
    """Actual destination disk admission before any expensive model load.

    Default closure holds raw states, their ZIP, raw evidence and evidence-only
    terminal ZIP together. Optional full export has its own larger actual guard.
    The frozen model material is already external and must already fit the disk.
    """
    from .evidence import EVIDENCE_CAP_BYTES,expansion_plan
    need(type(fixture) is bool,'explicit storage scope')
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    overhead=16*1024**2
    standard=2*CHECKPOINT_STORE_CAP+2*EVIDENCE_CAP_BYTES+2*overhead+DISK_RESERVE
    optional_full=4*CHECKPOINT_STORE_CAP+2*EVIDENCE_CAP_BYTES+2*overhead+DISK_RESERVE
    # Phase admission reserves actual future checkpoint obligations and one
    # bounded evidence phase; actual appends/exports keep independent guards.
    phase_growth=expansion_plan()['largest_planned_audit_json_upper_bytes']+512*1024**2
    required=(128*1024**2+DISK_RESERVE) if fixture else storage_plan()['estimated_checkpoint_upper_bytes']+phase_growth+DISK_RESERVE
    saved_cap=2*CHECKPOINT_STORE_CAP+2*EVIDENCE_CAP_BYTES+overhead+128*1024**2
    need(saved_cap<=20_000_000_000,'complete default retained outputs exceed published20GB provider quota')
    free=shutil.disk_usage(root).free
    need(free>=required,'insufficient actual disk for bounded states, checkpoint ZIP, evidence and terminal export plus4GiB reserve')
    return {'format':'owned-rl-session-disk-admission-v1','fixture':fixture,
        'observed_free_bytes':free,'required_free_bytes':required,'phase_evidence_growth_reserve_bytes':phase_growth,
        'saved_output_quota_bytes':20_000_000_000,'default_complete_saved_output_upper_bytes':saved_cap,
        'source_outer_allowance_bytes':128*1024**2,'worst_caps_are_not_upfront_free_space_requirement':True,
        'standard_worst_simultaneous_bytes_including_reserve':standard,
        'optional_full_export_worst_simultaneous_bytes_including_reserve':optional_full,
        'raw_checkpoint_cap_bytes':CHECKPOINT_STORE_CAP,'checkpoint_zip_cap_bytes':CHECKPOINT_STORE_CAP,
        'raw_evidence_cap_bytes':EVIDENCE_CAP_BYTES,'terminal_evidence_cap_bytes':EVIDENCE_CAP_BYTES+overhead,
        'zip_overhead_bytes_each':overhead,'free_reserve_bytes':DISK_RESERVE,
        'preexisting_frozen_model_material_copied':False,'actual_disk_checked':True}


def before_batch(root,*,fixture):
    """Reserve the next whole audit+durable state before rollout dispatch."""
    from .evidence import expansion_plan,pending_export_space
    need(type(fixture) is bool,'explicit batch storage scope')
    root=Path(root);plan=storage_plan()
    checkpoint=(16*1024**2 if fixture else plan['trained_payload_bytes']+METADATA_ALLOWANCE)
    audit=expansion_plan()['largest_planned_audit_json_upper_bytes']
    next_growth=checkpoint+audit+16*1024**2
    # New state/audit have one archive copy; compact state metadata has two.
    pending=pending_export_space(root)['total_pending_bytes']
    required=DISK_RESERVE+pending+2*next_growth+METADATA_ALLOWANCE
    free=shutil.disk_usage(root).free
    return {'format':'owned-rl-batch-disk-admission-v1','admitted':free>=required,
        'observed_free_bytes':free,'required_free_bytes':required,
        'next_bounded_growth_bytes':next_growth,'outstanding_export_bytes':pending,
        'reserve_bytes':DISK_RESERVE,'actual_disk_checked':True,'fixture':fixture}
