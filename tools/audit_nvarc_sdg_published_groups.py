"""Join complete retained static groups to published ordered parents; no exec."""
from __future__ import annotations
import argparse
import ast
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_sdg_artifacts import KEYS
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools.nvarc_qwen3_material import SOURCE
from tools.nvarc_source import verify

MANIFESTS=ROOT/'.irisx/nvarc-original/manifests'
STATIC=MANIFESTS/'sdg-program-static-20261002-002'
STATIC_PROOF=MANIFESTS/'sdg-program-static-verification-20261002-001/result.json'
PUBLISHED=MANIFESTS/'sdg-published-yield-20261002-001'
YIELD=MANIFESTS/'sdg-published-yield-summary-20261002-001/report.json'


def require(value,message):
    if not value:raise ValidationError(message)


def update_group(groups,row):
    key=tuple(row['join_key'][name] for name in KEYS)
    require(row['stage'] in {'inputs','outputs'} and all(isinstance(value,str) and value for value in key) and
        row['parent_ids']==sorted(set(key[-2:])) and row['filtered'] is False and row['program_semantics_verified'] is False,
        'exact retained response group/parent/no-execution binding required')
    group=groups.setdefault(key,{'inputs':0,'outputs':0,'sids':set(),'exposure_tags':row['exposure_tags']})
    require(group['exposure_tags']==row['exposure_tags'],'group exposure must remain unchanged')
    if row['stage']=='outputs':
        sid=row['sid'];require(type(sid) is int and 0<=sid<20 and sid not in group['sids'],
            'distinct original output SID in zero-through-nineteen range required')
        group['sids'].add(sid)
    else:require(row['sid'] is None and group['inputs']==0,'one retained input response per exact group required')
    group[row['stage']]+=1


def bind_member(member,groups,by_order):
    match=re.fullmatch(r'(nvarc_full|nvarc_training)/([0-9a-f]{8})/([0-9a-f]{8})_([0-9a-f]{8})\.json',member['path'])
    require(match is not None and match[2]==match[3] and member['ordered_parent_ids']==[match[3],match[4]] and
        member['parent_ids']==sorted(set(member['ordered_parent_ids'])) and
        member['filtered'] is False and member['program_semantics_verified'] is False,
        'exact original published ordered-parent path required')
    keys=by_order.get(tuple(member['ordered_parent_ids']),[])
    reverse=by_order.get(tuple(reversed(member['ordered_parent_ids'])),[])
    require(keys,'published member has no same-order raw input/output group')
    observations=[{'join_key':dict(zip(KEYS,key)),'input_responses':groups[key]['inputs'],
        'output_responses':groups[key]['outputs'],'output_sids':sorted(groups[key]['sids']),
        'sids_contiguous_from_zero':groups[key]['sids']==set(range(groups[key]['outputs'])),
        'exposure_tags':groups[key]['exposure_tags']} for key in sorted(keys)]
    require(all(row['exposure_tags']==member['exposure_tags'] for row in observations),'published/raw exposure differs')
    return {'path':member['path'],'published_sha256':member['sha256'],'pair_count':member['pair_count'],
        'ordered_parent_ids':member['ordered_parent_ids'],'parent_ids':member['parent_ids'],
        'exposure_tags':member['exposure_tags'],'same_order_groups':observations,
        'reversed_order_group_count':len(reverse),'selection_of_historical_mix_unknown':len(keys)!=1,
        'historical_generation_cli_known':False,'program_semantics_verified':False,'filter_replayed':False}


def summarize(observations,source_minimum):
    families=defaultdict(Counter);group_counts=Counter();eligible=Counter();pairs=Counter()
    for row in observations:
        family=row['path'].split('/')[0];groups=row['same_order_groups']
        families[family].update([','.join(map(str,sorted(group['output_responses'] for group in groups)))])
        group_counts[str(len(groups))]+=1;pairs[family]+=row['pair_count']
        eligible['has_group_at_source_default' if any(group['output_responses']>=source_minimum for group in groups)
            else 'no_group_at_source_default']+=1
    return {'published_puzzle_count':sum(group_counts.values()),'published_pair_count':sum(pairs.values()),
        'published_same_order_group_count_histogram':dict(group_counts),
        'output_response_count_sets_by_family':{family:dict(counts) for family,counts in families.items()},
        'default_minimum_output_response_coverage':dict(eligible),'source_default_minimum_output_programs':source_minimum,
        'historical_generation_cli_known':False,'selection_of_historical_mix_known':False,
        'program_semantics_verified':False,'source_8_12_4_filter_replayed':False,'correctness_scored':False,
        'new_ast_diagnostics':0,'generated_program_executions':0,'raw_parquet_reads':0,'teacher_calls':0,'model_calls':0,'paid_usd':0}


def audit(output):
    require(not output.exists(),'new immutable published-group evidence identity required')
    proof=json.loads(STATIC_PROOF.read_bytes());published=json.loads(YIELD.read_bytes())
    require(sha(STATIC_PROOF)=='b9320669b9fa411dbbf02078016909976ac71ccf0a13d90265604606dc091778' and
        proof['all_retained_rows_recounted'] is True and proof['all_parent_exposure_bindings_rechecked'] is True and
        sha(STATIC/'programs.jsonl')==proof['program_rows_sha256'] and
        sha(PUBLISHED/'members.jsonl')==published['members_sha256'] and published['members_verified']==103223,
        'exact complete static and published evidence prerequisites required')
    verify(SOURCE.parents[1],json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes()))
    source=SOURCE.parent/'SDG/scripts/generate_output_grids.py'
    tree=ast.parse(source.read_text(encoding='utf-8'));minimum=[]
    for node in ast.walk(tree):
        if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='add_argument' and
                node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value=='--min-solutions-per-puzzle'):
            minimum.extend(ast.literal_eval(key.value) for key in node.keywords if key.arg=='default')
    require(minimum==[20],'exact source CLI default required')
    output.mkdir(parents=True);started=time.monotonic();groups={};counts=Counter()
    (output/'analysis-source.py').write_bytes(Path(__file__).read_bytes())
    atomic(output/'analysis-source-binding.json',{'analysis_source_sha256':sha(output/'analysis-source.py'),
        'source_snapshot_timing':'before retained metadata iteration','new_program_executions':0,
        'new_ast_diagnostics':0,'new_raw_parquet_reads':0})
    ledger={'owner_decision':'Decision 0054','run_id':output.name,'state':'retained-metadata-join',
        'maximum_wall_seconds':1800,'rows_completed':0,'published_members_completed':0,'new_program_executions':0,
        'input_bindings':{'static_proof_sha256':sha(STATIC_PROOF),'program_rows_sha256':proof['program_rows_sha256'],
            'published_yield_sha256':sha(YIELD),'published_members_sha256':published['members_sha256'],
            'source_generate_output_grids_sha256':sha(source)}}
    atomic(output/'ledger.json',ledger)
    try:
        with (STATIC/'programs.jsonl').open(encoding='utf-8') as stream:
            for index,line in enumerate(stream):
                if index%8192==0:
                    require(time.monotonic()-started<1800,'finite metadata join resource bound reached')
                    ledger['rows_completed']=index;atomic(output/'ledger.json',ledger)
                row=json.loads(line);update_group(groups,row);counts[row['stage']]+=1
        require(dict(counts)==proof['rows_by_stage'],'all complete source response rows required')
        by_order=defaultdict(list)
        for key,group in groups.items():
            if group['outputs']:
                require(group['inputs']==1,'every raw output group must have its exact input')
                by_order[key[-2:]].append(key)
        require(sum(bool(group['outputs']) for group in groups.values())==proof['output_group_count'],
            'complete output group count differs')
        observations=[]
        with (PUBLISHED/'members.jsonl').open(encoding='utf-8') as stream,(output/'published-group-bindings.jsonl').open('wb') as destination:
            for index,line in enumerate(stream):
                if index%8192==0:require(time.monotonic()-started<1800,'finite published join resource bound reached')
                value=bind_member(json.loads(line),groups,by_order);observations.append(value)
                destination.write(canonical_bytes(value,newline=True))
        result={'format':'irisx/nvarc-published-output-group-join-v1',**summarize(observations,minimum[0]),
            'rows_by_stage':dict(counts),'raw_exact_group_count':len(groups),
            'bindings_sha256':sha(output/'published-group-bindings.jsonl'),'input_bindings':ledger['input_bindings'],
            'wall_seconds':time.monotonic()-started}
        require(result['published_puzzle_count']==103223 and result['published_pair_count']==2984385,
            'complete published count/pair coverage required')
        atomic(output/'result.json',result)
        ledger.update(state='complete-retained-metadata-join',rows_completed=sum(counts.values()),published_members_completed=len(observations))
        atomic(output/'ledger.json',ledger);return result
    except BaseException as error:
        ledger.update(state='incomplete-retained',error_type=type(error).__name__);atomic(output/'ledger.json',ledger);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(audit(args.output)))
