"""All published program response syntax/entry contracts, without execution.

This never interprets generated ASTs, regenerates teachers, accepts pairs, or
relabels structural diagnostics as dynamic program semantics.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import hashlib
import io
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
from irisx.arc_nvarc_sdg_artifacts import _source_functions,KEYS
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError
from tools.nvarc_source import verify
from tools.nvarc_qwen3_material import SOURCE


def inspect_program(code,entry):
    if not isinstance(code,str) or not code:return {'state':'missing-python-fence'}
    if len(code.encode('utf-8'))>1024**2:return {'state':'analysis-byte-ceiling'}
    try:tree=ast.parse(code)
    except (SyntaxError,RecursionError,ValueError):return {'state':'python-syntax-rejected'}
    functions=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==entry]
    imports=sorted({node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}|
        {alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names})
    if len(functions)!=1:return {'state':'missing-or-duplicate-entry','imports':imports}
    fn=functions[0];positional=fn.args.posonlyargs+fn.args.args
    minimum=len(positional)-len(fn.args.defaults)
    accepts_one=(minimum<=1 and (len(positional)>=1 or fn.args.vararg is not None) and
        not any(default is None for default in fn.args.kw_defaults))
    state=('async-entry' if isinstance(fn,ast.AsyncFunctionDef) else 'decorated-entry-unknown' if fn.decorator_list else
        'one-argument-contract' if accepts_one else 'one-argument-rejected')
    return {'state':state,'imports':imports,'positional_parameters':[a.arg for a in positional],
        'required_positional_parameters':minimum,'has_varargs':fn.args.vararg is not None,
        'accepts_one_positional_argument':accepts_one,'function_count':sum(isinstance(n,ast.FunctionDef) for n in tree.body)}


def carry_observation(previous,binding):
    """Reuse static diagnostics only for an exactly matching source response."""
    if any(previous.get(key)!=value for key,value in binding.items()):
        raise ValidationError('retained static response/parent binding differs')
    observed={key:value for key,value in previous.items() if key not in binding}
    if observed.get('state') not in {'missing-python-fence','analysis-byte-ceiling','python-syntax-rejected',
            'missing-or-duplicate-entry','async-entry','decorated-entry-unknown',
            'one-argument-contract','one-argument-rejected'}:
        raise ValidationError('retained static diagnostic state differs')
    return observed


def audit(output,reuse=None,maximum_wall_seconds=3600):
    import pyarrow.parquet as pq
    if output.exists():raise ValidationError('new immutable whole-program analysis identity required')
    material=ROOT/'.irisx/nvarc-original/materials/sdg-artifacts-20261002-resume-001'
    profile=ROOT/'.irisx/nvarc-original/manifests/sdg-full-profile-20261002-001'
    acquisition=json.loads((material/'acquisition.json').read_bytes())
    inventory=json.loads((material/'archive-inventory.json').read_bytes())
    metadata=json.loads((profile/'profile.json').read_bytes())
    if (acquisition['state']!='verified-published-raw-artifacts' or inventory['member_count']!=192 or
            sha_file(material/'archive-inventory.json')!=acquisition['inventory_sha256'] or
            sha_file(profile/'parent-lineage.jsonl')!=metadata['parent_lineage_sha256']):
        raise ValidationError('complete verified SDG material and parent metadata required')
    verify(SOURCE.parents[1],json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes()))
    parser=_source_functions(SOURCE.parent/'SDG/scripts/parser.py',('parse_python_code',),{'re':re})['parse_python_code']
    parents={}
    with (profile/'parent-lineage.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);key=tuple(row['parent_ids'])
            if key in parents:raise ValidationError('closed parent metadata differs')
            parents[key]=row
    expected={r['path']:r for r in inventory['members'] if r['path'].startswith(('inputs/','outputs/'))}
    if type(maximum_wall_seconds) is not int or not 3600<=maximum_wall_seconds<=10800:
        raise ValidationError('finite local static-analysis wall bound required')
    previous_ledger=previous_stream=previous_row=None;carried=0;new_analyses=0
    if reuse is not None:
        previous_ledger=json.loads((reuse/'ledger.json').read_bytes())
        source_binding=json.loads((reuse/'analysis-source-binding.json').read_bytes())
        if (previous_ledger['state']!='incomplete-retained' or
                previous_ledger['archive_inventory_sha256']!=acquisition['inventory_sha256'] or
                previous_ledger['parent_profile_sha256']!=metadata['parent_lineage_sha256'] or
                sha_file(reuse/'analysis-source.py')!=source_binding['analysis_sha256']):
            raise ValidationError('frozen incomplete static analysis with matching source required')
        def diagnostic_ast(path):
            nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body
                if isinstance(n,ast.FunctionDef) and n.name=='inspect_program']
            if len(nodes)!=1:raise ValidationError('unique retained static diagnostic implementation required')
            return ast.dump(nodes[0],include_attributes=False)
        if diagnostic_ast(reuse/'analysis-source.py')!=diagnostic_ast(Path(__file__)):
            raise ValidationError('static diagnostic semantics differ; no reuse allowed')
        previous_members=[json.loads(line) for line in (reuse/'members.jsonl').read_bytes().splitlines()]
        if (len(previous_members)!=previous_ledger['members_completed'] or
                any({k:v for k,v in row.items() if k!='rows_verified'}!=expected[name]
                    for row,(name,_) in zip(previous_members,sorted(expected.items())))):
            raise ValidationError('retained closed member prefix differs')
        previous_stream=(reuse/'programs.jsonl').open(encoding='utf-8')
        first_line=previous_stream.readline();previous_row=json.loads(first_line) if first_line else None
    output.mkdir(parents=True);started=time.monotonic();states={'inputs':Counter(),'outputs':Counter()}
    (output/'analysis-source.py').write_bytes(Path(__file__).read_bytes())
    atomic(output/'analysis-source-binding.json',{'source_path':'tools/audit_nvarc_sdg_programs.py',
        'analysis_sha256':sha_file(output/'analysis-source.py'),'generated_program_executions':0,
        'runtime_source_unchanged_since_launch':True})
    rows=Counter();imports=Counter();groups=Counter();input_groups=Counter();exposure=Counter()
    ledger={'owner_decision':'Decision 0054','run_id':output.name,'maximum_wall_seconds':maximum_wall_seconds,
        'maximum_member_bytes':1024**3,'members_total':len(expected),'members_reserved':0,'members_completed':0,
        'program_rows_completed':0,'generated_program_executions':0,'teacher_calls':0,'model_calls':0,
        'archive_inventory_sha256':acquisition['inventory_sha256'],
        'parent_profile_sha256':metadata['parent_lineage_sha256'],'state':'static-response-analysis'}
    if reuse is not None:
        ledger['recovery']={'previous_run':reuse.name,'program_rows_sha256':sha_file(reuse/'programs.jsonl'),
            'members_sha256':sha_file(reuse/'members.jsonl'),'ledger_sha256':sha_file(reuse/'ledger.json'),
            'analysis_source_sha256':source_binding['analysis_sha256'],
            'previous_program_rows_completed':previous_ledger['program_rows_completed'],
            'no_repeated_generated_program_execution':True,'same_static_diagnostic_semantics':True}
    atomic(output/'ledger.json',ledger)
    try:
        with zipfile.ZipFile(material/'nvarc-artifacts-puzzles.zip') as archive,(output/'programs.jsonl').open('wb') as stream:
            for name,member in sorted(expected.items()):
                if time.monotonic()-started>maximum_wall_seconds or member['bytes']>1024**3:
                    raise ValidationError('whole-program static analysis resource ceiling reached')
                ledger['members_reserved']+=1;atomic(output/'ledger.json',ledger)
                raw=archive.read(name)
                if len(raw)!=member['bytes'] or hashlib.sha256(raw).hexdigest()!=member['sha256']:
                    raise ValidationError('published program shard bytes differ')
                stage=name.split('/')[0];parquet=pq.ParquetFile(io.BytesIO(raw));count=0
                columns=[*KEYS,'completion']+(['sid'] if stage=='outputs' else [])
                for batch in parquet.iter_batches(batch_size=32,columns=columns):
                    for record in batch.to_pylist():
                        if time.monotonic()-started>maximum_wall_seconds:raise ValidationError('program row analysis wall ceiling reached')
                        key=tuple(record[k] for k in KEYS)
                        if (any(not isinstance(v,str) or not v for v in key) or
                                not isinstance(record['completion'],str)):
                            raise ValidationError('published program join/response contract differs')
                        parent=parents.get(tuple(sorted(set(key[-2:]))))
                        if parent is None:raise ValidationError('published program exposure join is absent')
                        completion=record['completion'];code=parser(completion)
                        binding={'member':name,'row':count,'stage':stage,'join_key':dict(zip(KEYS,key)),
                            'sid':record.get('sid'),'completion_sha256':hashlib.sha256(completion.encode()).hexdigest(),
                            'code_sha256':hashlib.sha256(code.encode()).hexdigest() if code else None,
                            'parent_ids':parent['parent_ids'],'exposure_tags':parent['exposure_tags'],
                            'filtered':False,'program_semantics_verified':False}
                        if previous_row is not None:
                            observed=carry_observation(previous_row,binding);carried+=1
                            next_line=previous_stream.readline();previous_row=json.loads(next_line) if next_line else None
                        else:
                            observed=inspect_program(code,'generate_puzzle_input' if stage=='inputs' else 'generate_puzzle_output')
                            new_analyses+=1
                        states[stage][observed['state']]+=1;imports.update(observed.get('imports',[]))
                        (input_groups if stage=='inputs' else groups)[key]+=1
                        exposure.update(parent['exposure_tags']);rows[stage]+=1;count+=1
                        stream.write(canonical_bytes({**binding,**observed},newline=True))
                        ledger['program_rows_completed']+=1
                if count!=parquet.metadata.num_rows:raise ValidationError('program shard full row coverage differs')
                if reuse is not None:
                    closed={row['path']:row['rows_verified'] for row in previous_members}
                    if name in closed and count!=closed[name]:
                        raise ValidationError('retained closed shard row count differs')
                with (output/'members.jsonl').open('ab') as index:
                    index.write(canonical_bytes({**member,'rows_verified':count},newline=True))
                del parquet,raw
                ledger['members_completed']+=1;atomic(output/'ledger.json',ledger)
        if (previous_row is not None or previous_ledger is not None and carried!=previous_ledger['program_rows_completed'] or
                dict(rows)!={stage:metadata['rows_by_stage'][stage] for stage in ('inputs','outputs')}):
            raise ValidationError('complete published program stage counts differ')
        report={'format':'irisx/nvarc-complete-program-static-profile-v1','rows_by_stage':dict(rows),
            'states_by_stage':{stage:dict(counter) for stage,counter in states.items()},
            'input_group_count':len(input_groups),'output_group_count':len(groups),
            'output_solution_count_histogram':{str(n):count for n,count in Counter(groups.values()).items()},
            'output_groups_without_input':len(set(groups)-set(input_groups)),
            'input_groups_without_output':len(set(input_groups)-set(groups)),
            'import_response_counts':dict(imports),'exposure_response_counts':dict(exposure),
            'all_input_output_shard_bytes_rechecked':True,'program_rows_sha256':sha_file(output/'programs.jsonl'),
            'source_python_parser_sha256':sha_file(SOURCE.parent/'SDG/scripts/parser.py'),
            'generated_program_executions':0,'teacher_calls':0,'model_calls':0,'pairs_accepted':0,
            'program_semantics_verified':False,'source_8_12_4_filter_replayed':False,
            'correctness_scored':False,'filter_applied':False,'maximum_paid_usd':0,
            'carried_static_diagnostics':carried,'new_static_diagnostics':new_analyses,
            'wall_seconds':time.monotonic()-started,'input_bindings':{k:ledger[k] for k in
                ('archive_inventory_sha256','parent_profile_sha256')}}
        atomic(output/'report.json',report);ledger['state']='complete-static-analysis';atomic(output/'ledger.json',ledger)
        print(json.dumps(report),flush=True)
    except BaseException as error:
        ledger.update(state='incomplete-retained',error_type=type(error).__name__);atomic(output/'ledger.json',ledger);raise
    finally:
        if previous_stream is not None:previous_stream.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',type=Path);parser.add_argument('--maximum-wall-seconds',type=int,default=3600)
    args=parser.parse_args();audit(args.output,args.reuse,args.maximum_wall_seconds)
