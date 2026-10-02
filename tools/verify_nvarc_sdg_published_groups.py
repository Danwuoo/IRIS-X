"""Independent raw-group/SID recount and complete published binding check."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_sdg_artifacts import KEYS
from irisx.canonical import digest_value
from irisx.errors import ValidationError

MANIFESTS=ROOT/'.irisx/nvarc-original/manifests'


def require(value,message):
    if not value:raise ValidationError(message)


def verify(folder):
    start=time.monotonic();result=json.loads((folder/'result.json').read_bytes())
    ledger=json.loads((folder/'ledger.json').read_bytes());source_binding=json.loads((folder/'analysis-source-binding.json').read_bytes())
    require(ledger['state']=='complete-retained-metadata-join' and
        ledger['rows_completed']==2244042 and ledger['published_members_completed']==103223 and
        sha(folder/'analysis-source.py')==source_binding['analysis_source_sha256'] and
        sha(folder/'published-group-bindings.jsonl')==result['bindings_sha256'] and
        ledger['input_bindings']==result['input_bindings'],'closed exact complete published-group join required')
    expected=result['input_bindings'];static=MANIFESTS/'sdg-program-static-20261002-002/programs.jsonl'
    published=MANIFESTS/'sdg-published-yield-20261002-001/members.jsonl'
    for name,path in {'program_rows_sha256':static,'published_members_sha256':published,
            'static_proof_sha256':MANIFESTS/'sdg-program-static-verification-20261002-001/result.json',
            'published_yield_sha256':MANIFESTS/'sdg-published-yield-summary-20261002-001/report.json',
            'source_generate_output_grids_sha256':ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source/NVARC/SDG/scripts/generate_output_grids.py'}.items():
        require(sha(path)==expected[name],'independent join input bytes differ')
    counts=Counter();raw=defaultdict(lambda:{'inputs':0,'outputs':0,'sids':set()});tags={}
    with static.open(encoding='utf-8') as stream:
        for index,line in enumerate(stream):
            if index%8192==0:require(time.monotonic()-start<1800,'finite independent metadata recount bound reached')
            row=json.loads(line);key=tuple(row['join_key'][k] for k in KEYS);stage=row['stage']
            require(stage in {'inputs','outputs'} and row['parent_ids']==sorted(set(key[-2:])) and
                row['filtered'] is False and row['program_semantics_verified'] is False,
                'source metadata group/parent binding differs')
            raw[key][stage]+=1;counts[stage]+=1
            if key in tags:require(tags[key]==row['exposure_tags'],'exact raw group exposure required')
            else:tags[key]=row['exposure_tags']
            if stage=='outputs':
                sid=row['sid'];require(type(sid) is int and 0<=sid<20 and sid not in raw[key]['sids'],'distinct source SID required')
                raw[key]['sids'].add(sid)
            else:require(row['sid'] is None and raw[key]['inputs']==1,'one exact raw input required')
    require(dict(counts)=={'inputs':193793,'outputs':2050249} and len(raw)==193793 and
        all(group['inputs']==1 for group in raw.values()),'complete raw metadata recount differs')
    ordered=defaultdict(list)
    for key,group in raw.items():
        if group['outputs']:ordered[key[-2:]].append(key)
    seen=set();families=defaultdict(Counter);sizes=Counter();eligible=Counter();pairs=0;reverse_counts=Counter()
    with published.open(encoding='utf-8') as originals,(folder/'published-group-bindings.jsonl').open(encoding='utf-8') as observations:
        for index,line in enumerate(originals):
            if index%8192==0:require(time.monotonic()-start<1800,'finite independent published recount bound reached')
            original=json.loads(line);observed=json.loads(next(observations));parents=tuple(original['ordered_parent_ids'])
            require(original['path'] not in seen and observed['path']==original['path'] and
                observed['published_sha256']==original['sha256'] and observed['pair_count']==original['pair_count'] and
                observed['ordered_parent_ids']==list(parents) and observed['parent_ids']==sorted(set(parents)) and
                observed['exposure_tags']==original['exposure_tags'] and observed['historical_generation_cli_known'] is False and
                observed['program_semantics_verified'] is False and observed['filter_replayed'] is False,
                'complete published observation path/source/parent/no-semantics differs')
            seen.add(original['path']);candidates=sorted(ordered[parents]);require(candidates,'same-order raw group required')
            require(observed['same_order_groups']==[{'join_key':dict(zip(KEYS,key)),
                'input_responses':raw[key]['inputs'],'output_responses':raw[key]['outputs'],'output_sids':sorted(raw[key]['sids']),
                'sids_contiguous_from_zero':raw[key]['sids']==set(range(raw[key]['outputs'])),
                'exposure_tags':tags[key]} for key in candidates] and
                observed['selection_of_historical_mix_unknown']==(len(candidates)!=1) and
                observed['reversed_order_group_count']==len(ordered[tuple(reversed(parents))]),
                'independently recounted source groups/SIDs/reversed parents differ')
            family=original['path'].split('/')[0];families[family].update([','.join(map(str,sorted(raw[key]['outputs'] for key in candidates)))])
            sizes[str(len(candidates))]+=1;reverse_counts[str(observed['reversed_order_group_count'])]+=1
            eligible['has_group_at_source_default' if max(raw[key]['outputs'] for key in candidates)>=20
                else 'no_group_at_source_default']+=1;pairs+=original['pair_count']
        require(next(observations,None) is None,'no extra published-group binding allowed')
    require(len(seen)==result['published_puzzle_count']==103223 and pairs==result['published_pair_count']==2984385 and
        result['raw_exact_group_count']==193793 and result['rows_by_stage']==dict(counts) and
        result['source_default_minimum_output_programs']==20 and
        result['published_same_order_group_count_histogram']==dict(sizes) and
        result['output_response_count_sets_by_family']=={k:dict(v) for k,v in families.items()} and
        result['default_minimum_output_response_coverage']==dict(eligible) and
        all(type(result[k]) is int and result[k]==0 for k in ('generated_program_executions','raw_parquet_reads',
            'new_ast_diagnostics','teacher_calls','model_calls','paid_usd')) and
        all(result[k] is False for k in ('historical_generation_cli_known','selection_of_historical_mix_known',
            'program_semantics_verified','source_8_12_4_filter_replayed','correctness_scored')),
        'recomputed published aggregation/cost/no-qualification differs')
    return {'format':'irisx/nvarc-independent-published-group-recount-v1','outcome':'complete',
        'result_sha256':sha(folder/'result.json'),'bindings_sha256':result['bindings_sha256'],
        'analysis_source_sha256':source_binding['analysis_source_sha256'],'rows_by_stage':dict(counts),
        'published_puzzle_count':len(seen),'published_pair_count':pairs,'published_group_count_histogram':dict(sizes),
        'default_minimum_output_response_coverage':dict(eligible),
        'output_response_count_sets_by_family':{k:dict(v) for k,v in families.items()},
        'every_raw_sid_and_ordered_parent_group_recounted':True,'every_published_binding_rechecked':True,
        'reversed_group_count_histogram':dict(reverse_counts),'source_8_12_4_filter_replayed':False,
        'historical_generation_cli_known':False,'program_semantics_verified':False,
        'raw_response_count_is_only_a_necessary_condition_for_twenty_usable_programs':True,
        'new_program_executions':0,'new_ast_diagnostics':0,'new_raw_parquet_reads':0,'teacher_calls':0,'model_calls':0,
        'wall_seconds':time.monotonic()-start}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(not args.output.exists(),'new immutable independent group proof required')
    value=verify(args.folder);atomic(args.output,value);print(json.dumps(value))
