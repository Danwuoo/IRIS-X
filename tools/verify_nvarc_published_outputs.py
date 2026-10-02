"""Recount every isolated attempt and independently reconstruct 8/12/4 votes."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools.replay_nvarc_published_outputs import CANARY


def require(value,message):
    if not value:raise ValidationError(message)


def majority_pairs(inputs,observed,minimum_majority=8,minimum_pairs=12,minimum_solutions=4):
    """No source predicate/program re-execution; count raw retained outcomes."""
    candidates=[];consistent=None;counts=[]
    for gid,value in enumerate(inputs):
        rows=observed[gid*10:(gid+1)*10]
        require(len(rows)==10,'ten exact per-input outcomes required')
        grids=[None if row['result']==value else row['result'] for row in rows]
        counter=Counter(canonical_bytes(grid) for grid in grids)
        best,number=counter.most_common(1)[0];grid=json.loads(best)
        counts.append(number)
        if grid is None or number<minimum_majority:continue
        sids={sid for sid,current in enumerate(grids) if canonical_bytes(current)==best}
        consistent=sids if consistent is None else consistent&sids
        candidates.append({'input':value,'output':grid})
        if not consistent:break
    if len(candidates)<minimum_pairs or len(consistent or set())<minimum_solutions:return [],counts,sorted(consistent or set())
    def diverse(values):
        return len({canonical_bytes(value) for value in values})>1 and len({color for value in values for row in value for color in row})>1
    if not diverse([row['input'] for row in candidates]) or not diverse([row['output'] for row in candidates]):return [],counts,sorted(consistent)
    return candidates,counts,sorted(consistent)


def verify(folder):
    terminal=json.loads((folder/'terminal.json').read_bytes())
    require(terminal['outcome'] in {'complete','failed'} and type(terminal['wall_seconds']) in (int,float) and
        math.isfinite(terminal['wall_seconds']) and 0<=terminal['wall_seconds']<=1800 and
        all(type(terminal[key]) is int and terminal[key]==0 for key in ('teacher_calls','model_calls','paid_usd','accepted_source_pairs')),
        'finite local zero-model/no-source-acceptance terminal required')
    if not (folder/'plan.json').is_file():
        require(terminal['outcome']=='failed' and terminal['program_attempts_reserved']==0,
            'no-plan failure cannot have program attempts')
        return {'outcome':'failed','program_attempts_reserved':0,'terminal_sha256':sha(folder/'terminal.json'),'new_program_attempts':0}
    plan=json.loads((folder/'plan.json').read_bytes());programs=json.loads((folder/'programs.json').read_bytes())
    pairs=json.loads((folder/'published-pairs.json').read_bytes());inputs=[pair['input'] for pair in pairs]
    require(plan['format']=='irisx/nvarc-published-output-diagnostic-v1' and plan['owner_decision']=='Decision 0054' and
        plan['run_id']==folder.name and plan['maximum_program_attempts']==301 and
        plan['maximum_wall_seconds']==1800 and plan['maximum_execution_seconds']==1200 and
        all(type(plan[key]) is int and plan[key]==0 for key in
            ('maximum_teacher_calls','maximum_model_calls','maximum_paid_usd','accepted_source_pairs')) and
        plan['source_filter']=={'minimum_majority':8,'minimum_pairs':12,'minimum_correct_solutions':4} and
        plan['source_minimum_output_programs']==20 and plan['retained_output_programs']==10 and
        len(inputs)==30 and len(programs)==10 and plan['source_twenty_program_precondition_passed'] is False and
        plan['input_generation_replayed'] is False and plan['helper_removal_replayed'] is False and
        plan['accepted_source_pairs']==0 and plan['arc_correctness_scored'] is False,
        'exact fixed ten-program published-input diagnostic scope required')
    require(set(plan['material_inventory'])=={'material-verification.json','programs.json','published-pairs.json',
        'raw-responses.json','replay-source.py','selection.json'},'closed local diagnostic material inventory required')
    for name,digest in plan['material_inventory'].items():require(sha(folder/name)==digest,'retained replay material differs')
    selection=json.loads((folder/'selection.json').read_bytes())
    require(plan['selection']==selection['binding'] and
        plan['selection']['path']=='nvarc_full/0934a4d8/0934a4d8_00576224.json' and
        plan['replay_source_sha256']==plan['material_inventory']['replay-source.py'],
        'exact selected first published group and executed source required')
    wanted=[{'stage':'trusted-isolation-canary','gid':None,'sid':None,'input_digest':digest_value([[0]]),
        'code_sha256':hashlib.sha256(CANARY.encode()).hexdigest()}]
    wanted.extend({'stage':'published-output-diagnostic','gid':gid,'sid':sid,'input_digest':digest_value(value),
        'code_sha256':hashlib.sha256(code.encode()).hexdigest()} for gid,value in enumerate(inputs) for sid,code in enumerate(programs))
    require(plan['forward_schedule']==wanted,'exact independent isolated attempt schedule differs')
    events=[json.loads(line) for line in (folder/'invocations.jsonl').read_bytes().splitlines()]
    observed=[json.loads(line) for line in (folder/'program-results.jsonl').read_bytes().splitlines()]
    require(0<=len(observed)<=len(events)<=301 and len(events)-len(observed)<=1,'closed reserved/returned attempt prefix required')
    for i,event in enumerate(events):
        require(event=={**wanted[i],'attempt':i+1,'completed':False} and type(event['attempt']) is int,
            'actual program reservation/order differs')
    for i,row in enumerate(observed):
        require(type(row['attempt']) is int and row['attempt']==i+1 and row['outcome'] in {'returned-grid','sandbox-rejected'} and
            row['result_digest']==digest_value(row['result']) and
            ((row['outcome']=='sandbox-rejected') == (row['result'] is None)),'retained actual outcome/digest differs')
        if row['result'] is not None:
            grid=row['result'];require(isinstance(grid,list) and 1<=len(grid)<=30 and len({len(line) for line in grid})==1 and
                all(isinstance(line,list) and 1<=len(line)<=30 and all(type(x) is int and 0<=x<=9 for x in line) for line in grid),
                'closed legal returned grid required')
    if len(events)>1:require(observed[0]['outcome']=='returned-grid' and observed[0]['result']==[[1]],'trusted isolation canary must pass first')
    require(type(terminal['program_attempts_reserved']) is int and terminal['program_attempts_reserved']==len(events),
        'terminal reservation count contradicts actual prefix')
    if terminal['outcome']=='failed':
        require(type(terminal['returned_observations']) is int and terminal['returned_observations']==len(observed),
            'failed terminal return count contradicts actual prefix')
    result={'format':'irisx/nvarc-published-output-diagnostic-verification-v1','outcome':terminal['outcome'],
        'plan_digest':digest_value(plan),'terminal_sha256':sha(folder/'terminal.json'),
        'program_attempts_reserved':len(events),'returned_observations':len(observed),
        'new_program_attempts':0,'teacher_calls':0,'model_calls':0,'accepted_source_pairs':0,
        'whole_sdg_method_completed':False,'arc_correctness_scored':False}
    if terminal['outcome']=='complete':
        require(len(events)==len(observed)==301,'complete exact 301-attempt observation required')
        grids=[None if row['result']==inputs[i//10] else row['result'] for i,row in enumerate(observed[1:])]
        filtered,counts,sids=majority_pairs(inputs,observed[1:])
        require(filtered==json.loads((folder/'diagnostic-filter-result.json').read_bytes()),'source 8/12/4 result contradicts independent raw votes')
        fields={'program_attempts_reserved':301,'trusted_canary_attempts':1,'output_program_attempts':300,
            'sandbox_rejections':sum(row['outcome']=='sandbox-rejected' for row in observed[1:]),
            'returned_grid_observations':sum(row['outcome']=='returned-grid' for row in observed[1:]),
            'valid_nonidentity_outputs':sum(value is not None for value in grids),
            'individual_outputs_agree_with_published':sum(value==pairs[i//10]['output'] for i,value in enumerate(grids)),
            'diagnostic_8_12_4_pair_count':len(filtered),'filtered_pairs_match_published':filtered==pairs}
        require(all(type(terminal[key]) is type(value) and terminal[key]==value for key,value in fields.items()) and
            terminal['plan_digest']==digest_value(plan) and terminal['source_twenty_program_precondition_passed'] is False and
            terminal['whole_sdg_method_completed'] is False and terminal['input_generation_replayed'] is False and
            terminal['helper_removal_replayed'] is False and json.loads((folder/'result.json').read_bytes())==terminal,
            'independent diagnostic counters/qualification differs')
        result.update(**fields,majority_votes_by_processed_input=counts,consistent_solution_sids=sids,
            result_sha256=sha(folder/'result.json'),every_program_reservation_and_grid_recounted=True,
            source_twenty_program_precondition_passed=False)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(not args.output.exists(),'new immutable independent local replay proof required')
    value=verify(args.folder);atomic(args.output,value);print(json.dumps(value))
