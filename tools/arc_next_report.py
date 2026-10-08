"""Separate sealed-output development scoring and small evidence export.

Scoring never changes solver records, ranks, training weights or configuration.
Only held-out PUBLIC-TRAINING demonstrations from the new material package are
accepted. This is an engineering screen, not official/public-evaluation scoring.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import stat
import zipfile


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(body):return hashlib.sha256(body).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())

def ranked_prefix(candidates,*,max_tokens=None,max_seconds=None):
    unique={}
    for c in candidates:
        usage=c['usage_at_admission']
        if max_tokens is not None and usage['prompt_tokens']+usage['generated_tokens']>max_tokens:continue
        if max_seconds is not None and c['admitted_at_seconds']>max_seconds:continue
        key=c['digest']
        if key not in unique:unique[key]={**c,'votes':0}
        unique[key]['votes']+=1
    return sorted(unique.values(),key=lambda c:(-c['votes'],c['call_id'],c['digest']))

def metrics(ranked,answers):
    top1=top2=oracle=0
    for index,answer in enumerate(answers):
        distinct=[]
        for c in ranked:
            g=c['outputs'][index]
            if g not in distinct:distinct.append(g)
        top1+=bool(distinct and distinct[0]==answer)
        top2+=answer in distinct[:2]
        oracle+=answer in distinct
    return {'top1':top1,'top2':top2,'pool_oracle':oracle,'tests':len(answers)}

def score_development(output_dir,data_root):
    """Read answers only after verifying frozen records and stopped supervision."""
    output=Path(output_dir);data=Path(data_root)
    supervisor=read(output.parent/(output.name+'-supervision.json'))
    if supervisor.get('confirmed_stopped') is not True:raise ValueError('Owned solver process must be stopped first')
    receipt=read(output/'receipt.json')
    if supervisor.get('child_receipt')!=receipt:raise ValueError('Supervisor does not bind this frozen child receipt')
    if receipt.get('format')!='irisx/arc-next-architecture-receipt-v1':raise ValueError('Exact architecture receipt required')
    for name,expected in receipt['files'].items():
        if Path(name).name!=name or sha((output/name).read_bytes())!=expected:raise ValueError('Frozen result member changed')
    challenges=read(data/'development-challenges.json');groups=read(data/'task-groups.json')
    if sha((data/'development-challenges.json').read_bytes())!=receipt['challenges_sha256']:
        raise ValueError('Development input binding differs')
    if set(challenges)!=set(groups['development_ids']) or set(challenges)&set(groups['training_ids']):
        raise ValueError('Task-disjoint public-training development group required')
    from tools.arc_next_training import load_training_material
    from tools.arc_kaggle_submission import grid,challenge_counts
    tasks,training_manifest=load_training_material(data/'train-demonstrations.json',data/'training-manifest.json')
    if set(training_manifest['task_partition']['dev'])!=set(challenges):raise ValueError('Development tasks differ from frozen training partition')
    counts=challenge_counts(challenges)
    for task_id,task in challenges.items():
        source=tasks[task_id]['train']
        if task!={'train':source[:-1],'test':[{'input':source[-1]['input']}]}:raise ValueError('Development challenge differs from held-out source demonstration')
    answers=read(data/'evaluator/development-solutions.json')
    if set(answers)!=set(challenges):raise ValueError('Full development denominator required')
    for task_id,items in answers.items():
        if type(items) is not list or len(items)!=counts[task_id]:raise ValueError('Answer/test denominator differs')
        for answer in items:grid(answer)
        if items!=[tasks[task_id]['train'][-1]['output']]:raise ValueError('Development answer differs from frozen training-source demonstration')
    token_points=(4096,8192,16384,32768,36864)
    time_points=(30,60,120)
    result={'format':'irisx/arc-next-development-aggregate-v1',
      'source_scope':'held-out public-training demonstrations only',
      'task_count':len(challenges),'test_count':sum(len(t['test']) for t in challenges.values()),
      'official_score':None,'public_evaluation_score':None,'promotion':False,
      'cost_comparison':'Matched observed candidate prefixes; prompt+generated tokens are a proxy, not equal FLOPs. Time includes model and interpreter work.',
      'arms':{}}
    for arm in ('grid','program','repair'):
        totals={'top1':0,'top2':0,'pool_oracle':0,'tests':result['test_count'],'completed_task_records':0,
                'calls':0,'prompt_tokens':0,'generated_tokens':0,'program_steps':0,'wall_seconds':0.0,
                'unknown_usage_records':0,'token_frontier':{},'time_frontier':{}}
        for points,label in ((token_points,'token_frontier'),(time_points,'time_frontier')):
            totals[label]={str(v):{'top1':0,'top2':0,'pool_oracle':0,'tests':result['test_count']} for v in points}
        for task_id,task in challenges.items():
            path=output/(task_id+'-'+arm+'.json')
            if not path.is_file():
                if path.name in receipt['files']:raise ValueError('Sealed result is missing')
                continue
            if path.name not in receipt['files']:raise ValueError('Unsealed task-arm result cannot be scored')
            record=read(path)
            if record['task_id']!=task_id or record['arm']!=arm:raise ValueError('Result identity mismatch')
            item=record['result'];totals['completed_task_records']+=1
            total=metrics(ranked_prefix(item['candidates']),answers[task_id])
            for key in ('top1','top2','pool_oracle'):totals[key]+=total[key]
            totals['calls']+=len(item['calls']);totals['wall_seconds']+=item['elapsed_seconds']
            totals['unknown_usage_records']+=not item['usage_known']
            for key in ('prompt_tokens','generated_tokens','program_steps'):totals[key]+=item['usage'][key]
            for point in token_points:
                v=metrics(ranked_prefix(item['candidates'],max_tokens=point),answers[task_id])
                for key in ('top1','top2','pool_oracle'):totals['token_frontier'][str(point)][key]+=v[key]
            for point in time_points:
                v=metrics(ranked_prefix(item['candidates'],max_seconds=point),answers[task_id])
                for key in ('top1','top2','pool_oracle'):totals['time_frontier'][str(point)][key]+=v[key]
        result['arms'][arm]=totals
    result['receipt_sha256']=sha((output/'receipt.json').read_bytes())
    return result


def export_report(output_dir):
    root=Path(output_dir).absolute()
    if not root.is_dir() or any(p.is_symlink() for p in (root,*root.parents)):
        raise ValueError('Regular completed/partial run directory required')
    if (root/'preflight.json').is_file():
        terminal=read(root/'watchdog-result.json')
        cleanup=terminal.get('cleanup',{})
        if cleanup.get('worker_alive_after_cleanup') is not False or cleanup.get('group_still_observable_after_kill') is not False:
            raise ValueError('Training worker/group stop is not confirmed; do not archive live evidence')
    elif (root/'input-binding.json').is_file():
        terminal=read(root.parent/(root.name+'-supervision.json'))
        if terminal.get('confirmed_stopped') is not True:raise ValueError('Architecture worker stop is not confirmed')
    else:raise ValueError('Expected IRIS-X run evidence marker is absent')
    archive=root.parent/(root.name+'-evidence.zip')
    if archive.exists():raise ValueError('Archive already exists; do not overwrite evidence')
    files=[]
    for path in sorted(root.iterdir()):
        if path.is_symlink():raise ValueError('Evidence symlinks forbidden')
        if path.is_file() and path.suffix in ('.json','.jsonl','.log'):
            if any(term in path.name.lower() for term in ('solution','credential','secret','tokenizer')):
                raise ValueError('Unexpected evaluator/credential/model file in report root')
            files.append((path.name,path))
    for suffix in ('-supervision.json','-process.log','-development-aggregate.json'):
        path=root.parent/(root.name+suffix)
        if path.exists():
            if path.is_symlink() or not path.is_file():raise ValueError('Regular owned supervision evidence required')
            files.append(('supervision/'+path.name,path))
    manifest={'format':'irisx/arc-next-evidence-archive-v1','weights_included':False,'solutions_included':False,'files':{}}
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as z:
        for name,path in files:
            before=path.stat();h=hashlib.sha256();count=0
            with path.open('rb') as inp,z.open(name,'w',force_zip64=True) as out:
                for chunk in iter(lambda:inp.read(1024*1024),b''):
                    h.update(chunk);count+=len(chunk);out.write(chunk)
            after=path.stat()
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino) or count!=before.st_size:
                raise ValueError('Live evidence changed during archive; partial archive retained')
            manifest['files'][name]={'sha256':h.hexdigest(),'bytes':count}
        z.writestr('__manifest__.json',canonical(manifest))
    h=hashlib.sha256()
    with archive.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return {'archive':str(archive),'sha256':h.hexdigest(),'bytes':archive.stat().st_size,
            'weights_included':False,'solutions_included':False,
            'adapter_location':str(root/'adapter') if (root/'adapter').is_dir() else None}
