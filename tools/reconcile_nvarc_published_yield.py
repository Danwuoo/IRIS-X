"""Full published puzzle/parent/stage reconciliation without teacher execution.

All published bytes and exposure are retained, including observed anomalies.
This measures published yield and source structural predicates, not regenerated
program semantics, eight-vote agreement or four-solution consistency.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.arc_nvarc_sdg_artifacts import _source_functions
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError
from tools.nvarc_source import verify
from tools.nvarc_qwen3_material import SOURCE


def inspect_pairs(pairs, validate_grids):
    issues=[]
    if not isinstance(pairs,list) or not pairs or any(not isinstance(p,dict) or set(p)!={'input','output'} for p in pairs):
        return {'pair_count':len(pairs) if isinstance(pairs,list) else None,'issues':['pair-schema']}
    for side in ('input','output'):
        values=[pair[side] for pair in pairs]
        valid=all(isinstance(grid,list) and 1<=len(grid)<=30 and all(isinstance(row,list) and 1<=len(row)<=30
            and all(type(color) is int and 0<=color<=9 for color in row) for row in grid) for grid in values)
        rectangular=valid and all(len({len(row) for row in grid})==1 for grid in values)
        if not rectangular:issues.append(side+'-grid-contract')
        # Invoke only the checked upstream pure predicate, never generated code.
        if valid and not validate_grids(values):issues.append(side+'-source-diversity-predicate')
    if len(pairs)<12:issues.append('below-source-minimum-twelve-pairs')
    return {'pair_count':len(pairs),'issues':issues}


def reconcile(output):
    started=time.monotonic()
    if output.exists():raise ValidationError('new immutable local yield identity required')
    manifest=json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes())
    verify(SOURCE.parents[1],manifest)
    functions=_source_functions(SOURCE.parent/'SDG/scripts/make_pairs.py',('validate_grids',),{'Grid':list})
    predicate=functions['validate_grids']
    profile=ROOT/'.irisx/nvarc-original/manifests/sdg-full-profile-20261002-001'
    meta=json.loads((profile/'profile.json').read_bytes())
    if sha_file(profile/'parent-lineage.jsonl')!=meta['parent_lineage_sha256']:
        raise ValidationError('complete original parent profile differs')
    parents={}
    with (profile/'parent-lineage.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);key=tuple(row['parent_ids'])
            if key in parents:raise ValidationError('duplicate parent profile')
            parents[key]=row
    inventory_path=ROOT/'.irisx/nvarc-data/synthetic-v1-inventory.json'
    inventory=json.loads(inventory_path.read_bytes())
    archive_path=ROOT/'.irisx/nvarc-data/raw/synthetic-v1/nvarc-synthetic-puzzles.zip'
    if inventory['member_count']!=103223 or sha_file(archive_path)!=inventory['archive_sha256']:
        raise ValidationError('complete fixed published synthetic archive required')
    output.mkdir(parents=True)
    ledger={'run_id':output.name,'owner_decision':'Decision 0054','members_reserved':0,'members_completed':0,
        'maximum_wall_seconds':1800,'maximum_member_bytes':4*1024**2,'program_executions':0,'teacher_calls':0,
        'inventory_sha256':sha_file(inventory_path),'parent_profile_sha256':meta['parent_lineage_sha256']}
    atomic(output/'ledger.json',ledger)
    families,counts,issues,exposure,stage_coverage=Counter(),Counter(),Counter(),Counter(),Counter()
    published_parent_sets=set();pair_total=0
    try:
        with zipfile.ZipFile(archive_path) as archive,(output/'members.jsonl').open('wb') as stream:
            expected={item['path']:item for item in inventory['members']}
            if {item.filename:item.file_size for item in archive.infolist() if not item.is_dir()}!={name:item['bytes'] for name,item in expected.items()}:
                raise ValidationError('closed published inventory differs')
            for i,(name,member) in enumerate(sorted(expected.items())):
                if i%256==0:
                    ledger['members_reserved']=min(i+256,len(expected));atomic(output/'ledger.json',ledger)
                if time.monotonic()-started>1800 or member['bytes']>ledger['maximum_member_bytes']:
                    raise ValidationError('yield reconciliation resource ceiling reached')
                match=re.fullmatch(r'(nvarc_full|nvarc_training)/([0-9a-f]{8})/([0-9a-f]{8})_([0-9a-f]{8})\.json',name)
                if match is None or match[2]!=match[3]:raise ValidationError('published original ordered-parent path differs')
                raw=archive.read(name)
                if len(raw)!=member['bytes'] or hashlib.sha256(raw).hexdigest()!=member['sha256']:
                    raise ValidationError('published puzzle member bytes differ')
                ordered=[match[3],match[4]];key=tuple(sorted(set(ordered)))
                profile_row=parents.get(key)
                data=inspect_pairs(json.loads(raw),predicate)
                tags=profile_row['exposure_tags'] if profile_row else ['unresolved-artifact-parent-set']
                stages=profile_row['records_by_stage'] if profile_row else {}
                families[match[1]]+=1;counts[data['pair_count']]+=1;issues.update(data['issues']);exposure.update(tags)
                for stage in ('mixtures','inputs','outputs'):
                    stage_coverage[stage+'-present' if stages.get(stage,0) else stage+'-absent']+=1
                pair_total+=data['pair_count'] or 0;published_parent_sets.add(key)
                stream.write(canonical_bytes({'path':name,'sha256':member['sha256'],'ordered_parent_ids':ordered,
                    'parent_ids':list(key),'exposure_tags':tags,'raw_artifact_rows_by_stage':stages,
                    **data,'filtered':False,'program_semantics_verified':False},newline=True))
                ledger['members_completed']=i+1
                if (i+1)%256==0:atomic(output/'ledger.json',ledger)
        report={'format':'irisx/nvarc-complete-published-yield-v1','members_verified':ledger['members_completed'],
            'published_puzzle_count':sum(families.values()),'published_pair_count':pair_total,
            'family_counts':dict(families),'pair_count_histogram':{str(k):v for k,v in counts.items()},'observed_issues':dict(issues),
            'exposure_counts':dict(exposure),'raw_stage_coverage':dict(stage_coverage),
            'published_unique_parent_sets':len(published_parent_sets),'raw_unique_parent_sets':len(parents),
            'raw_parent_sets_without_published_puzzle':len(set(parents)-published_parent_sets),
            'published_parent_sets_absent_from_raw_profile':len(published_parent_sets-set(parents)),
            'raw_rows_by_stage':meta['rows_by_stage'],'program_executions':0,'teacher_calls':0,
            'program_semantics_verified':False,'source_majority_and_consistent_solution_gates_replayed':False,
            'filter_applied':False,'correctness_scored':False,'maximum_paid_usd':0,
            'members_sha256':sha_file(output/'members.jsonl'),'source_filter_sha256':sha_file(SOURCE.parent/'SDG/scripts/make_pairs.py'),
            'wall_seconds':time.monotonic()-started,'input_bindings':{k:ledger[k] for k in ('inventory_sha256','parent_profile_sha256')}}
        atomic(output/'report.json',report);ledger['state']='complete-no-execution';atomic(output/'ledger.json',ledger)
        print(json.dumps(report),flush=True)
    except BaseException as error:
        ledger.update(state='incomplete-retained',error_type=type(error).__name__);atomic(output/'ledger.json',ledger);raise


def recover_report(retained,output):
    """Reconstruct counters from a completed, immutable member observation.

    No puzzle bytes or generated programs are rerun. Each retained member's
    inventory and parent/stage bindings are independently reconstructed.
    """
    started=time.monotonic()
    if output.exists():raise ValidationError('new immutable summary identity required')
    ledger=json.loads((retained/'ledger.json').read_bytes())
    if ledger.get('members_completed')!=103223 or ledger.get('members_reserved')!=103223:
        raise ValidationError('complete retained member observation required')
    inventory_path=ROOT/'.irisx/nvarc-data/synthetic-v1-inventory.json'
    profile=ROOT/'.irisx/nvarc-original/manifests/sdg-full-profile-20261002-001'
    meta=json.loads((profile/'profile.json').read_bytes())
    if (sha_file(inventory_path)!=ledger['inventory_sha256'] or
            sha_file(profile/'parent-lineage.jsonl')!=ledger['parent_profile_sha256'] or
            meta['parent_lineage_sha256']!=ledger['parent_profile_sha256']):
        raise ValidationError('retained input bindings differ')
    verify(SOURCE.parents[1],json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes()))
    inventory=json.loads(inventory_path.read_bytes())
    expected={row['path']:row for row in inventory['members']}
    parents={}
    with (profile/'parent-lineage.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);key=tuple(row['parent_ids'])
            if key in parents:raise ValidationError('duplicate parent profile')
            parents[key]=row
    families,counts,issues,exposure,coverage=Counter(),Counter(),Counter(),Counter(),Counter()
    seen=set();published=set();total=0
    with (retained/'members.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);name=row['path'];match=re.fullmatch(
                r'(nvarc_full|nvarc_training)/([0-9a-f]{8})/([0-9a-f]{8})_([0-9a-f]{8})\.json',name)
            if name in seen or name not in expected or match is None or match[2]!=match[3]:
                raise ValidationError('retained closed member names differ')
            ordered=[match[3],match[4]];key=tuple(sorted(set(ordered)));parent=parents.get(key)
            tags=parent['exposure_tags'] if parent else ['unresolved-artifact-parent-set']
            stages=parent['records_by_stage'] if parent else {}
            if (row['sha256']!=expected[name]['sha256'] or row['ordered_parent_ids']!=ordered or
                    row['parent_ids']!=list(key) or row['exposure_tags']!=tags or
                    row['raw_artifact_rows_by_stage']!=stages or row['filtered'] is not False or
                    row['program_semantics_verified'] is not False or
                    type(row['pair_count']) is not int or row['pair_count']<0 or
                    not isinstance(row['issues'],list) or any(not isinstance(v,str) for v in row['issues'])):
                raise ValidationError('retained member bindings differ')
            seen.add(name);published.add(key);families[match[1]]+=1;counts[row['pair_count']]+=1
            total+=row['pair_count'];issues.update(row['issues']);exposure.update(tags)
            for stage in ('mixtures','inputs','outputs'):
                coverage[stage+'-present' if stages.get(stage,0) else stage+'-absent']+=1
    if seen!=set(expected):raise ValidationError('retained member observation incomplete')
    report={'format':'irisx/nvarc-complete-published-yield-v1','members_verified':len(seen),
        'published_puzzle_count':sum(families.values()),'published_pair_count':total,
        'family_counts':dict(families),'pair_count_histogram':{str(k):v for k,v in counts.items()},
        'observed_issues':dict(issues),'exposure_counts':dict(exposure),'raw_stage_coverage':dict(coverage),
        'published_unique_parent_sets':len(published),'raw_unique_parent_sets':len(parents),
        'raw_parent_sets_without_published_puzzle':len(set(parents)-published),
        'published_parent_sets_absent_from_raw_profile':len(published-set(parents)),
        'raw_rows_by_stage':meta['rows_by_stage'],'program_executions':0,'teacher_calls':0,
        'program_semantics_verified':False,'source_majority_and_consistent_solution_gates_replayed':False,
        'filter_applied':False,'correctness_scored':False,'maximum_paid_usd':0,
        'members_sha256':sha_file(retained/'members.jsonl'),
        'source_filter_sha256':sha_file(SOURCE.parent/'SDG/scripts/make_pairs.py'),
        'wall_seconds':time.monotonic()-started,
        'input_bindings':{k:ledger[k] for k in ('inventory_sha256','parent_profile_sha256')},
        'retained_observation':{'run_id':ledger['run_id'],'ledger_sha256':sha_file(retained/'ledger.json'),
            'state':ledger['state'],'scope':'original run verified every puzzle byte and inspected source predicates; recovery independently reconstructs all closed member, parent, exposure, stage and aggregate bindings without rerunning puzzle predicates'}}
    output.mkdir(parents=True);atomic(output/'report.json',report)
    atomic(output/'ledger.json',{'run_id':output.name,'state':'complete-local-summary','program_executions':0,
        'teacher_calls':0,'members_reconciled':len(seen),'report_sha256':sha_file(output/'report.json')})
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--retained',type=Path)
    args=parser.parse_args()
    if args.retained:recover_report(args.retained,args.output)
    else:reconcile(args.output)
