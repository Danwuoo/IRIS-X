"""Independently recount closed static evidence; never run generated code."""
from __future__ import annotations
import argparse
import ast
from collections import Counter
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
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError
from tools import audit_nvarc_sdg_programs as analysis

STATES={'missing-python-fence','analysis-byte-ceiling','python-syntax-rejected','missing-or-duplicate-entry',
    'async-entry','decorated-entry-unknown','one-argument-contract','one-argument-rejected'}


def require(condition,message):
    if not condition:raise ValidationError(message)


def recount(folder,members,parents,maximum_wall_seconds=1800):
    """Check every retained row in closed source-member order without new AST."""
    require(type(maximum_wall_seconds) is int and 1<=maximum_wall_seconds<=1800,'bounded independent static verification required')
    started=time.monotonic();digest=hashlib.sha256();counts=Counter();stage_rows=Counter()
    states={'inputs':Counter(),'outputs':Counter()};imports=Counter();exposure=Counter()
    groups={'inputs':Counter(),'outputs':Counter()};parent_counts={'inputs':Counter(),'outputs':Counter()}
    order={r['path']:i for i,r in enumerate(members)};last=-1
    require(len(order)==len(members),'unique closed static members required')
    with (folder/'programs.jsonl').open('rb') as stream:
        while raw:=stream.readline(4*1024**2+1):
            require(len(raw)<=4*1024**2 and raw.endswith(b'\n') and time.monotonic()-started<maximum_wall_seconds,
                'bounded static row or verification wall ceiling reached')
            digest.update(raw);row=json.loads(raw);member=row['member']
            require(member in order and order[member]>=last,'closed ordered static response members differ')
            last=order[member];stage=member.split('/')[0]
            require(stage in states and type(row['row']) is int and row['row']==counts[member] and
                row['stage']==stage and row['state'] in STATES,'complete static member row index/stage/state differs')
            common={'member','row','stage','join_key','sid','completion_sha256','code_sha256',
                'parent_ids','exposure_tags','filtered','program_semantics_verified','state'}
            simple={'missing-python-fence','analysis-byte-ceiling','python-syntax-rejected'}
            diagnostic=(set() if row['state'] in simple else {'imports'} if
                row['state']=='missing-or-duplicate-entry' else {'imports','positional_parameters',
                    'required_positional_parameters','has_varargs','accepts_one_positional_argument','function_count'})
            require(set(row)==common|diagnostic,'closed static digest/diagnostic row schema differs')
            require(set(row['join_key'])==set(KEYS) and all(isinstance(row['join_key'][key],str) and
                row['join_key'][key] for key in KEYS),'exact five-field static response join required')
            key=tuple(row['join_key'][key] for key in KEYS);parent=parents.get(tuple(sorted(set(key[-2:]))))
            require(parent is not None and row['parent_ids']==parent['parent_ids'] and
                row['exposure_tags']==parent['exposure_tags'] and row['filtered'] is False and
                row['program_semantics_verified'] is False,'static response parent/exposure/no-semantics binding differs')
            require(isinstance(row['completion_sha256'],str) and re.fullmatch('[0-9a-f]{64}',row['completion_sha256']) and
                (row['code_sha256'] is None and row['state']=='missing-python-fence' or
                 isinstance(row['code_sha256'],str) and re.fullmatch('[0-9a-f]{64}',row['code_sha256'])),
                'retained response/program digest contract differs')
            imported=row.get('imports',[])
            require(isinstance(imported,list) and all(isinstance(v,str) for v in imported) and
                imported==sorted(set(imported)),'static import diagnostics differ')
            counts[member]+=1;stage_rows[stage]+=1;states[stage][row['state']]+=1
            imports.update(imported);exposure.update(row['exposure_tags']);groups[stage][key]+=1
            parent_counts[stage][tuple(parent['parent_ids'])]+=1
    require(all(type(row['rows_verified']) is int and row['rows_verified']>=0 and
        counts[row['path']]==row['rows_verified'] for row in members),'complete static closed-shard row counts differ')
    require(all(parent_counts[stage][key]==parent['records_by_stage'].get(stage,0)
        for key,parent in parents.items() for stage in ('inputs','outputs')),
        'every independent parent/stage response count differs')
    return {'rows_by_stage':dict(stage_rows),'states_by_stage':{k:dict(v) for k,v in states.items()},
        'input_group_count':len(groups['inputs']),'output_group_count':len(groups['outputs']),
        'output_solution_count_histogram':{str(n):count for n,count in Counter(groups['outputs'].values()).items()},
        'output_groups_without_input':len(set(groups['outputs'])-set(groups['inputs'])),
        'input_groups_without_output':len(set(groups['inputs'])-set(groups['outputs'])),
        'import_response_counts':dict(imports),'exposure_response_counts':dict(exposure),
        'program_rows_sha256':digest.hexdigest()}


def verify(folder):
    material=ROOT/'.irisx/nvarc-original/materials/sdg-artifacts-20261002-resume-001'
    profile=ROOT/'.irisx/nvarc-original/manifests/sdg-full-profile-20261002-001'
    acquisition=json.loads((material/'acquisition.json').read_bytes())
    inventory=json.loads((material/'archive-inventory.json').read_bytes())
    metadata=json.loads((profile/'profile.json').read_bytes())
    ledger=json.loads((folder/'ledger.json').read_bytes());report=json.loads((folder/'report.json').read_bytes())
    require(acquisition['state']=='verified-published-raw-artifacts' and inventory['member_count']==192 and
        sha(material/'archive-inventory.json')==acquisition['inventory_sha256']==ledger['archive_inventory_sha256'] and
        sha(profile/'parent-lineage.jsonl')==metadata['parent_lineage_sha256']==ledger['parent_profile_sha256'],
        'verified raw inventory and complete parent metadata bindings required')
    require(sha(profile/'members.jsonl')==metadata['member_metadata_sha256'],
        'independent raw-Parquet header observations differ')
    headers=[json.loads(line) for line in (profile/'members.jsonl').read_bytes().splitlines()]
    header_map={row['path']:row for row in headers}
    require(len(header_map)==len(headers)==192 and
        sorted(({k:row[k] for k in ('path','bytes','sha256')} for row in headers),key=lambda r:r['path'])==
        sorted(inventory['members'],key=lambda r:r['path']),'closed independent raw-Parquet metadata differs')
    require(report['format']=='irisx/nvarc-complete-program-static-profile-v1' and
        ledger['state']=='complete-static-analysis' and ledger['owner_decision']=='Decision 0054' and
        ledger['run_id']==folder.name and ledger['members_reserved']==ledger['members_completed']==ledger['members_total']==170,
        'complete frozen whole-response static ledger required')
    zero={'generated_program_executions':0,'teacher_calls':0,'model_calls':0,'pairs_accepted':0,
        'program_semantics_verified':False,'source_8_12_4_filter_replayed':False,'correctness_scored':False,
        'filter_applied':False,'maximum_paid_usd':0}
    require(all(canonical_bytes(report.get(k))==canonical_bytes(v) for k,v in zero.items()) and
        all(type(ledger[k]) is int and ledger[k]==0 for k in ('generated_program_executions','teacher_calls','model_calls')),
        'static-only exact zero model/program/score/cost scope required')
    members=[json.loads(line) for line in (folder/'members.jsonl').read_bytes().splitlines()]
    expected=sorted((r for r in inventory['members'] if r['path'].startswith(('inputs/','outputs/'))),key=lambda r:r['path'])
    require([{k:v for k,v in r.items() if k!='rows_verified'} for r in members]==expected,
        'every retained static shard identity differs')
    require(all(type(row['rows_verified']) is int and row['rows_verified']==header_map[row['path']]['parquet_rows']
        for row in members),'every static shard count must match independently read raw-Parquet headers')
    binding=json.loads((folder/'analysis-source-binding.json').read_bytes())
    require(sha(folder/'analysis-source.py')==binding['analysis_sha256'],'frozen analysis source bytes differ')
    def diagnostic(path):
        nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='inspect_program']
        require(len(nodes)==1,'unique static diagnostic implementation required')
        return ast.dump(nodes[0],include_attributes=False)
    require(diagnostic(folder/'analysis-source.py')==diagnostic(Path(analysis.__file__)),
        'retained static diagnostic function AST differs')
    parents={}
    with (profile/'parent-lineage.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);key=tuple(row['parent_ids'])
            require(key not in parents,'unique closed parent metadata required');parents[key]=row
    recomputed=recount(folder,members,parents)
    require(all(canonical_bytes(report.get(k))==canonical_bytes(v) for k,v in recomputed.items()) and
        recomputed['rows_by_stage']=={k:metadata['rows_by_stage'][k] for k in ('inputs','outputs')} and
        ledger['program_rows_completed']==sum(recomputed['rows_by_stage'].values()),
        'independent complete static recount differs from terminal report')
    require(report['input_bindings']=={k:ledger[k] for k in ('archive_inventory_sha256','parent_profile_sha256')} and
        report['source_python_parser_sha256']==sha(analysis.SOURCE.parent/'SDG/scripts/parser.py') and
        report['all_input_output_shard_bytes_rechecked'] is True,
        'exact source parser/raw-shard observation bindings differ')
    recovery=ledger.get('recovery');carried=0
    if recovery is not None:
        name=recovery['previous_run'];require('/' not in name and '\\' not in name and ':' not in name and name not in {'.','..'},
            'safe previous static identity required')
        previous=folder.parent/name
        require(previous.resolve().is_relative_to(folder.parent.resolve()),'previous static path escapes evidence root')
        for filename,key in (('programs.jsonl','program_rows_sha256'),('members.jsonl','members_sha256'),
                ('ledger.json','ledger_sha256'),('analysis-source.py','analysis_source_sha256')):
            require(sha(previous/filename)==recovery[key],'immutable preceding static evidence differs')
        prior=json.loads((previous/'ledger.json').read_bytes());carried=prior['program_rows_completed']
        require(prior['state']=='incomplete-retained' and carried==recovery['previous_program_rows_completed'] and
            recovery['same_static_diagnostic_semantics'] is True and recovery['no_repeated_generated_program_execution'] is True,
            'exact incomplete preceding static prefix required')
    require(report['carried_static_diagnostics']==carried and
        type(report['new_static_diagnostics']) is int and report['new_static_diagnostics']+carried==ledger['program_rows_completed'],
        'complete carried/new static coverage differs')
    return {'format':'irisx/nvarc-independent-static-recount-v1','run_id':folder.name,'outcome':'complete',
        'report_sha256':sha(folder/'report.json'),'ledger_sha256':sha(folder/'ledger.json'),
        'analysis_source_sha256':binding['analysis_sha256'],'members_sha256':sha(folder/'members.jsonl'),
        **recomputed,'all_retained_rows_recounted':True,'all_parent_exposure_bindings_rechecked':True,
        'all_parent_stage_counts_rechecked':True,'all_independent_raw_parquet_header_counts_rechecked':True,
        'new_ast_diagnostics':0,'new_raw_parquet_reads':0,'carried_static_diagnostics':carried,**zero,
        'proof_scope':'closed retained static evidence recount; source-response AST observations were made by the bound audit, not repeated here'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(not args.output.exists(),'new independent static recount output required')
    proof=verify(args.folder);atomic(args.output,proof);print(json.dumps(proof))
