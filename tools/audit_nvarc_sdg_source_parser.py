"""Run only trusted original parser functions on two frozen response groups."""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.nvarc_qwen3_material import SOURCE
from tools.nvarc_source import verify as verify_source

BASE=ROOT/'.irisx/nvarc-original'
RUNTIME=BASE/'materials/sdg-source-parser-runtime-20261002-002'
GROUP20=BASE/'runs/nvarc-overnight-sdg-replay-003'
GROUP10=BASE/'runs/nvarc-original-published-output-replay-001'


def require(value,message):
    if not value:raise ValidationError(message)


def static_program(parser,code,stage,sid):
    """Pass text to trusted parsing/cleanup; never import or execute that text."""
    row={'stage':stage,'sid':sid,'original_code_sha256':hashlib.sha256(code.encode()).hexdigest()}
    try:
        before=parser.parse_functions(code)
        cleaned=parser.remove_unused_functions(code) if stage=='outputs' else code
        after=parser.parse_functions(cleaned)
        entry='generate_puzzle_output' if stage=='outputs' else 'generate_puzzle_input'
        row.update(state='parsed',functions_before=sorted(before),functions_after=sorted(after),
            cleaned_code_sha256=hashlib.sha256(cleaned.encode()).hexdigest(),
            code_unchanged=cleaned==code,removed_function_names=sorted(set(before)-set(after)),
            python_ast_unchanged=ast.dump(ast.parse(code),include_attributes=False)==
                ast.dump(ast.parse(cleaned),include_attributes=False),
            literal_source_entry_present='def '+entry+'(' in cleaned,
            input_test_names=sorted(name for name in before if name.startswith('test_')))
        return row,cleaned
    except Exception as error:
        row.update(state='source-parser-rejected',error_type=type(error).__name__,error_message=str(error)[:500])
        return row,None


def audit(output):
    require(not output.exists(),'new immutable static parser audit required')
    verify_source(SOURCE.parents[1],json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes()))
    require(sha(GROUP20/'programs.json')=='0ca0384b1ae6f40061f0f6766d3d1aad685caf762314c7657735ea18116c8fd1' and
        sha(GROUP10/'independent-verification-002.json')=='98a678d18b60165fb1de1ac876fb668667b04e234d27d5f85c3da4969a934a68',
        'exact fixed complete replay prerequisites required')
    versions={name:importlib.metadata.version(name) for name in ('tree-sitter','tree-sitter-python')}
    require(versions=={'tree-sitter':'0.23.2','tree-sitter-python':'0.23.6'},'exact compatible parser versions required')
    acquisition=json.loads((RUNTIME/'acquisition.json').read_bytes())
    require(sha(RUNTIME/'acquisition.json')=='56a649165d0a289a27c9246315c9039e13cb9f7a0b9361ef98ab751ca3822534' and
        acquisition['state']=='complete-compatible-parser-runtime' and acquisition['historical_versions_known'] is False,
        'verified compatible parser material required')
    wanted_wheels={'tree_sitter-0.23.2-cp312-cp312-win_amd64.whl',
        'tree_sitter_python-0.23.6-cp39-abi3-win_amd64.whl'}
    require({p.name for p in RUNTIME.iterdir()}==wanted_wheels|
        {'acquisition.json','tree-sitter-primary.json','tree-sitter-python-primary.json'},
        'closed two-wheel parser material required')
    for name,digest in acquisition['carried_inventory'].items():
        require(sha(RUNTIME/name)==digest,'frozen carried parser material differs')
    for row in acquisition['events']:
        require(row['state']=='retained','closed exact parser acquisition required')
        name=row.get('filename',row['project']+'-primary.json')
        require(sha(RUNTIME/name)==row['sha256'],'frozen acquired parser material differs')
    matched_wheels=set()
    for metadata in RUNTIME.glob('*-primary.json'):
        data=json.loads(metadata.read_bytes())
        for wheel in RUNTIME.glob('*.whl'):
            matching=[item for item in data['urls'] if item['filename']==wheel.name]
            if matching:
                require(len(matching)==1 and wheel.stat().st_size==matching[0]['size'] and
                    sha(wheel)==matching[0]['digests']['sha256'],'primary wheel bytes differ')
                matched_wheels.add(wheel.name)
    require(matched_wheels==wanted_wheels,'both primary version wheel records required')
    output.mkdir(parents=True);started=time.monotonic()
    script=SOURCE.parent/'SDG/scripts/parser.py'
    module=ModuleType('irisx_trusted_pinned_sdg_parser');module.__file__=str(script)
    # Only the independently Git-verified upstream parser is imported here.
    exec(compile(script.read_text(encoding='utf-8'),str(script),'exec'),module.__dict__)
    old=json.loads((GROUP20/'programs.json').read_bytes());new=json.loads((GROUP10/'programs.json').read_bytes())
    groups=[]
    for label,input_code,codes in [('first-raw-twenty-response-group',old['input'],old['outputs']),
        ('first-published-ten-response-group',None,new)]:
        require(time.monotonic()-started<120,'finite static parser ceiling reached')
        rows=[];cleaned=[]
        if input_code is not None:
            row,_=static_program(module,input_code,'inputs',None);rows.append(row)
        for sid,code in enumerate(codes):
            row,value=static_program(module,code,'outputs',sid);rows.append(row);cleaned.append(value)
        prefix=0
        for row in [row for row in rows if row['stage']=='outputs']:
            if row['state']!='parsed' or not row['literal_source_entry_present']:break
            prefix+=1
        groups.append({'selection':label,'retained_response_count':len(codes),
            'source_usable_prefix':prefix,'current_twenty_program_precondition_passed':prefix>=20,
            'all_output_codes_unchanged':all(row.get('code_unchanged',False) for row in rows if row['stage']=='outputs'),
            'all_output_python_asts_unchanged':all(row.get('python_ast_unchanged',False) for row in rows if row['stage']=='outputs'),
            'rows':rows})
        atomic(output/(label+'-cleaned-programs.json'),cleaned)
    result={'format':'irisx/nvarc-sdg-source-parser-audit-v1','outcome':'complete','owner_decision':'Decision 0054',
        'versions':versions,'historical_parser_versions_known':False,'maximum_wall_seconds':120,
        'source_parser_sha256':sha(script),'runtime_acquisition_sha256':sha(RUNTIME/'acquisition.json'),
        'input_material_sha256':{'twenty_programs':sha(GROUP20/'programs.json'),'ten_programs':sha(GROUP10/'programs.json')},
        'groups':groups,'program_executions':0,'teacher_calls':0,'model_calls':0,'paid_usd':0,
        'generated_code_executed_on_host':False,'dynamic_semantics_verified':False,'whole_archive_verified':False,
        'wall_seconds':time.monotonic()-started,'audit_source_sha256':sha(Path(__file__))}
    atomic(output/'result.json',result);(output/'audit-source.py').write_bytes(Path(__file__).read_bytes())
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    result=audit(args.output)
    print(json.dumps({**{key:value for key,value in result.items() if key!='groups'},
        'groups':[{key:value for key,value in group.items() if key!='rows'} for group in result['groups']]}))
