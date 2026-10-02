"""One frozen ten-response group on published inputs, isolated and diagnostic."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_sdg import WSLNamespaceProgramExecutor
from irisx.arc_nvarc_sdg_artifacts import _source_functions,KEYS
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools.nvarc_qwen3_material import SOURCE
from tools.nvarc_source import verify as verify_source

BASE=ROOT/'.irisx/nvarc-original'
SELECTION=BASE/'proposals/published-output-replay-20261002-001/selection.json'
GROUPS=BASE/'manifests/sdg-published-groups-20261002-001'
RAW=BASE/'materials/sdg-artifacts-20261002-resume-001'
CANARY='import numpy as np\ndef generate_puzzle_output(grid):\n    return np.array([[1]],dtype=np.int8)\n'


def require(value,message):
    if not value:raise ValidationError(message)


def source_filter(folder,inputs,grids,codes):
    """Only pinned upstream pure filtering executes on the host."""
    import pandas as pd
    import numpy as np
    relative=Path('diagnostic/0934a4d8/0934a4d8_00576224.json')
    input_path=folder/'filter-input'/relative;output_path=folder/'filter-output'/relative
    input_path.parent.mkdir(parents=True);output_path.parent.mkdir(parents=True)
    atomic(input_path,[[i+1,value] for i,value in enumerate(inputs)])
    atomic(output_path,{'grids':grids,'codes':codes})
    import builtins,os
    source=_source_functions(SOURCE.parent/'SDG/scripts/make_pairs.py',
        ('filter_solutions','validate_grids','grid_to_string','string_to_grid'),
        {'os':os,'glob':SimpleNamespace(glob=lambda pattern:[output_path.as_posix()]),
            'json':json,'np':np,'pd':pd,'tqdm':lambda values:values,'Grid':list[list[int]],
            'open':lambda path,mode='r':builtins.open(path,mode,encoding='utf-8')})
    destination=folder/'diagnostic-filter-pairs'
    source['filter_solutions']((folder/'filter-input').as_posix(),output_path.as_posix(),destination.as_posix(),8,12,4)
    return json.loads((destination/relative).read_bytes()) if (destination/relative).exists() else []


def materialize(folder):
    import pyarrow.parquet as pq
    selection=json.loads(SELECTION.read_bytes());binding=selection['binding'];responses=selection['responses']
    first=json.loads((GROUPS/'published-group-bindings.jsonl').open(encoding='utf-8').readline())
    require(binding==first and binding['path']=='nvarc_full/0934a4d8/0934a4d8_00576224.json' and
        len(binding['same_order_groups'])==1 and binding['same_order_groups'][0]['output_responses']==10 and
        [row['sid'] for row in responses]==list(range(10)) and len({row['member'] for row in responses})==1,
        'first frozen published ten-response group required')
    require(sha(GROUPS/'independent-verification.json')=='dafaba7addf62618e291f0132f695dbffbccfe38e7f3eb00f885062b8d185f79',
        'complete independently verified raw/published group prerequisite required')
    require(sha(GROUPS/'published-group-bindings.jsonl')=='d9632d61143a742759dad93283f27920f5df3fc67bba1e9ab89f939d04e9d5c8' and
        sha(RAW/'archive-inventory.json')=='97239ee8456229a8bd393ceddcc04495b6634ea40b24d20ad175fb794d35d588',
        'exact complete raw/published retained inventories required')
    inventory=json.loads((RAW/'archive-inventory.json').read_bytes());member={row['path']:row for row in inventory['members']}[responses[0]['member']]
    require(member['bytes']<=1024**3,'one bounded exact source Parquet member required')
    with zipfile.ZipFile(RAW/'nvarc-artifacts-puzzles.zip') as archive:raw=archive.read(member['path'])
    require(len(raw)==member['bytes'] and hashlib.sha256(raw).hexdigest()==member['sha256'],'exact raw source shard required')
    parquet=pq.ParquetFile(io.BytesIO(raw));wanted={row['row']:row for row in responses};records={};offset=0
    for batch in parquet.iter_batches(batch_size=128,columns=[*KEYS,'sid','completion']):
        for i,record in enumerate(batch.to_pylist()):
            if offset+i in wanted:records[offset+i]=record
        offset+=batch.num_rows
        if len(records)==10:break
    parser=_source_functions(SOURCE.parent/'SDG/scripts/parser.py',('parse_python_code',),{'re':__import__('re')})['parse_python_code']
    codes=[];kept=[]
    for observed in responses:
        record=records[observed['row']];completion=record['completion'];code=parser(completion)
        require({key:record[key] for key in KEYS}==binding['same_order_groups'][0]['join_key'] and
            record['sid']==observed['sid'] and hashlib.sha256(completion.encode()).hexdigest()==observed['completion_sha256'] and
            code is not None and hashlib.sha256(code.encode()).hexdigest()==observed['code_sha256'] and
            len(code.encode())<=65536,'exact selected completion/code/SID binding required')
        codes.append(code);kept.append(record)
    with zipfile.ZipFile(ROOT/'.irisx/nvarc-data/raw/synthetic-v1/nvarc-synthetic-puzzles.zip') as archive:
        pairs_raw=archive.read(binding['path'])
    require(hashlib.sha256(pairs_raw).hexdigest()==binding['published_sha256'],'exact published pair bytes required')
    pairs=json.loads(pairs_raw);require(len(pairs)==30 and all(set(pair)=={'input','output'} for pair in pairs),
        'thirty public synthetic pairs required')
    atomic(folder/'material-verification.json',{'source_member':member,'raw_parquet_reads':1,
        'selected_responses':10,'published_path':binding['path'],'published_sha256':binding['published_sha256'],
        'selected_response_binding_sha256':sha(SELECTION)})
    atomic(folder/'selection.json',selection);atomic(folder/'raw-responses.json',kept)
    atomic(folder/'programs.json',codes);atomic(folder/'published-pairs.json',pairs)
    return binding,codes,pairs


def replay(folder):
    require(not folder.exists() and folder.name=='nvarc-original-published-output-replay-001','new fixed local diagnostic identity required')
    verify_source(SOURCE.parents[1],json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes()))
    folder.mkdir(parents=True);started=time.monotonic();phase='material-verification';events=[];results=[]
    (folder/'replay-source.py').write_bytes(Path(__file__).read_bytes())
    atomic(folder/'ledger.json',{'owner_decision':'Decision 0054','run_id':folder.name,'state':'material-verification',
        'maximum_wall_seconds':1800,'maximum_program_attempts':301,'program_attempts_reserved':0,'teacher_calls':0,'model_calls':0,'paid_usd':0})
    try:
        binding,codes,pairs=materialize(folder);executor=WSLNamespaceProgramExecutor();inputs=[pair['input'] for pair in pairs]
        schedule=[{'stage':'trusted-isolation-canary','gid':None,'sid':None,'input_digest':digest_value([[0]]),'code_sha256':hashlib.sha256(CANARY.encode()).hexdigest()}]
        schedule.extend({'stage':'published-output-diagnostic','gid':gid,'sid':sid,'input_digest':digest_value(value),
            'code_sha256':hashlib.sha256(code.encode()).hexdigest()} for gid,value in enumerate(inputs) for sid,code in enumerate(codes))
        plan={'format':'irisx/nvarc-published-output-diagnostic-v1','owner_decision':'Decision 0054','run_id':folder.name,
            'selection':binding,'selection_sha256':sha(SELECTION),'maximum_wall_seconds':1800,'maximum_execution_seconds':1200,
            'maximum_program_attempts':301,'forward_schedule':schedule,'maximum_teacher_calls':0,'maximum_model_calls':0,
            'maximum_paid_usd':0,'source_minimum_output_programs':20,'retained_output_programs':10,
            'source_twenty_program_precondition_passed':False,'input_generation_replayed':False,'helper_removal_replayed':False,
            'source_filter':{'minimum_majority':8,'minimum_pairs':12,'minimum_correct_solutions':4},
            'namespace_script_sha256':sha(ROOT/'tools/nvarc_sdg_namespace.sh'),'executor_source_sha256':sha(ROOT/'src/irisx/arc_nvarc_sdg.py'),
            'replay_source_sha256':sha(folder/'replay-source.py'),'source_filter_sha256':sha(SOURCE.parent/'SDG/scripts/make_pairs.py'),
            'material_inventory':{path.name:sha(path) for path in folder.iterdir() if path.is_file() and path.name!='ledger.json'},
            'arc_correctness_scored':False,'accepted_source_pairs':0,'historical_generation_cli_known':False,
            'scope':'fixed published-input/output-program diagnostic only; no complete SDG acceptance'}
        atomic(folder/'plan.json',plan);deadline=time.monotonic()+1200;phase='isolated-output-diagnostic'
        for wanted in schedule:
            require(time.monotonic()<deadline-30 and time.monotonic()-started<1800-60,'finite isolated replay wall ceiling reached')
            require(sha(ROOT/'tools/nvarc_sdg_namespace.sh')==plan['namespace_script_sha256'] and
                sha(ROOT/'src/irisx/arc_nvarc_sdg.py')==plan['executor_source_sha256'],'immutable isolated execution boundary required')
            event={**wanted,'attempt':len(events)+1,'completed':False};events.append(event)
            atomic(folder/'ledger.json',{'owner_decision':'Decision 0054','run_id':folder.name,'state':phase,
                'maximum_program_attempts':301,'program_attempts_reserved':len(events),'schedule_digest':digest_value(schedule),
                'teacher_calls':0,'model_calls':0,'paid_usd':0})
            with (folder/'invocations.jsonl').open('ab') as stream:stream.write(canonical_bytes(event,newline=True))
            code=CANARY if wanted['sid'] is None else codes[wanted['sid']]
            value=[[0]] if wanted['gid'] is None else inputs[wanted['gid']]
            try:
                returned=executor.execute_entry(code,'generate_puzzle_output',input_grid=value,source_numpy=True)
                observation={'attempt':event['attempt'],'outcome':'returned-grid','result':returned,'result_digest':digest_value(returned)}
            except ValidationError as error:
                observation={'attempt':event['attempt'],'outcome':'sandbox-rejected','result':None,'result_digest':digest_value(None),'cause':str(error)[:1200]}
            results.append(observation)
            with (folder/'program-results.jsonl').open('ab') as stream:stream.write(canonical_bytes(observation,newline=True))
            if wanted['sid'] is None:require(observation['outcome']=='returned-grid' and returned==[[1]],'trusted WSL canary must pass before any generated program')
        grids=[{'gid':event['gid'],'sid':event['sid'],'grid':None if observation['result']==inputs[event['gid']] else observation['result']}
            for event,observation in zip(events[1:],results[1:])]
        filtered=source_filter(folder,inputs,grids,codes);atomic(folder/'diagnostic-filter-result.json',filtered)
        result={'format':plan['format']+'-result','outcome':'complete','plan_digest':digest_value(plan),
            'program_attempts_reserved':len(events),'trusted_canary_attempts':1,'output_program_attempts':300,
            'sandbox_rejections':sum(row['outcome']=='sandbox-rejected' for row in results[1:]),
            'returned_grid_observations':sum(row['outcome']=='returned-grid' for row in results[1:]),
            'valid_nonidentity_outputs':sum(row['grid'] is not None for row in grids),
            'individual_outputs_agree_with_published':sum(row['grid']==pairs[row['gid']]['output'] for row in grids),
            'diagnostic_8_12_4_pair_count':len(filtered),'filtered_pairs_match_published':filtered==pairs,
            'source_twenty_program_precondition_passed':False,'accepted_source_pairs':0,'input_generation_replayed':False,
            'helper_removal_replayed':False,'whole_sdg_method_completed':False,'arc_correctness_scored':False,
            'teacher_calls':0,'model_calls':0,'paid_usd':0,'wall_seconds':time.monotonic()-started}
        atomic(folder/'result.json',result);atomic(folder/'terminal.json',result);return result
    except BaseException as error:
        atomic(folder/'terminal.json',{'outcome':'failed','phase':phase,'error_type':type(error).__name__,'error_message':str(error)[:1200],
            'program_attempts_reserved':len(events),'returned_observations':len(results),'teacher_calls':0,'model_calls':0,'paid_usd':0,
            'accepted_source_pairs':0,'wall_seconds':time.monotonic()-started});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(replay(args.output)))
