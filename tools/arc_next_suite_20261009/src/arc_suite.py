"""IRIS-X ten-stage suite: inert by default, truth-isolated and budget-ledgered.

Model output is interpreted only by the pinned bounded AST interpreter in a
separate limited CPU worker. Gold is read only by score() after confirmed stop
and sealed solver evidence. Nothing executes on import or disabled launch.
"""
from __future__ import annotations
import hashlib
import importlib.util
import importlib.machinery
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

RUNTIME_MANIFEST_SHA = 'c2e7913e8ae208deb26e06f37fcd76c79c1a87b6c49ffb3de7b2ee054fee7e67'
VERIFIER_SHA = 'e8e9994de69449d0602907c87e48a3e7bc5c43ee19b9c211fb06e8845bac15bc'
N1_SOURCE_SHA = '22af738c8a63d3078fa704fa0140ce278192a6032b77ce5030cdc09bfcf3f0d5'
AGENT_SHA = '410713680242c0af12f4216181cd0a6318f46788e98e0577b4bfb67b9d2fc911'
DESIGN_SHA = 'b8c10fac57a3c9e5c9a44a04d29d5a9567f8909cc88d7d79f9359462b84ed4eb'
PROGRAM_SHA = 'fbcf0c933561067b6c9b4fc1e4c44048f02bbd8348ba312d06da37b3f22ebba7'
AUDIT_SHA = 'f116345a059aa0cb2abadbd1bf2e1c8faa65c32b076fd4c6bea2d028fa5f0931'
TRAIN_INSTRUCTION = ('Infer the grid transformation from the demonstrations. Return only the complete '
                     'output grid as a JSON array of integer rows, without explanation.\nDemonstrations:\n')
EXPECTED_PINS = {'adapter': {'manifest_sha256': '7215085857a3caacbe32302a9b6e77b4ad9524fee2a5a621c39dacb02ee2e9d0', 'private': True, 'reference': 'danielwuu/iris-arc-granite42-run003-adapter-20261009/1'}, 'interpreter': {'manifest_sha256': '20a52944f1ee2abf6f47a2e3beafce44951993439fede39335e660cea143495e', 'private': True, 'reference': 'danielwuu/iris-arc-next-cpython312-offline/2'}, 'model': {'manifest_sha256': 'cd845822cd2c0ca749dd3e6f580f51e68b91c0e5c5886fe239fc3c14f5bb0b99', 'private': True, 'reference': 'danielwuu/iris-arc-granite42-8b-offline/2'}, 'runtime': {'manifest_sha256': 'c2e7913e8ae208deb26e06f37fcd76c79c1a87b6c49ffb3de7b2ee054fee7e67', 'private': True, 'reference': 'danielwuu/iris-arc-next-runtime/8'}, 'wheels': {'manifest_sha256': '2b082a3c36534b5602b8a9f738beec2c01b3d2df11b5438f1c352a84c118b052', 'private': True, 'reference': 'danielwuu/iris-arc-next-cu128-cp312-wheels/1'}}
SAMPLING = {'do_sample': True, 'temperature': .7, 'top_p': .95, 'enable_thinking': False}

MAX_NEW=2048
MAX_PROMPT=6144
MAX_CONTEXT=8192
SLOTS=4
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_bytes())

def write(path, value):
    """Durable append-only file commit. An identity cannot be silently replaced."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.pending-' + uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        stream.write(canonical(value) + b'\n'); stream.flush(); os.fsync(stream.fileno())
    try: os.link(temporary, path)
    finally: temporary.unlink()

def grid(value):
    if (type(value) is not list or not 1 <= len(value) <= 30
            or any(type(row) is not list for row in value) or not 1 <= len(value[0]) <= 30
            or any(len(row) != len(value[0]) for row in value)
            or any(type(cell) is not int or not 0 <= cell <= 9 for row in value for cell in row)):
        raise ValueError('Expected rectangular 1..30 integer grid, colors 0..9')
    return value

def task(value):
    if type(value) is not dict or set(value) != {'train', 'test'}:
        raise ValueError('Only solver-visible train and test fields admitted')
    if type(value['train']) is not list or not 1 <= len(value['train']) <= 10:
        raise ValueError('One to ten visible demonstrations required')
    if type(value['test']) is not list or len(value['test']) != 1:
        raise ValueError('Exactly one ordered query required')
    for pair in value['train']:
        if type(pair) is not dict or set(pair) != {'input', 'output'}: raise ValueError('Invalid demonstration')
        grid(pair['input']); grid(pair['output'])
    if type(value['test'][0]) is not dict or set(value['test'][0]) != {'input'}:
        raise ValueError('Query truth or metadata forbidden')
    grid(value['test'][0]['input'])
    return json.loads(canonical(value))

def _runtime_tools(runtime, *, verify_all=False):
    runtime = Path(runtime).resolve()
    code = runtime / 'runtime'
    if verify_all:
        manifest = runtime / 'bundle-manifest.json'
        if file_sha(manifest) != RUNTIME_MANIFEST_SHA: raise ValueError('Original runtime8 manifest pin differs')
        data = read(manifest); entries = data['files']
        if any(p.is_symlink() for p in runtime.rglob('*')): raise ValueError('Symlink runtime forbidden')
        actual = {p.relative_to(runtime).as_posix() for p in runtime.rglob('*') if p.is_file()}
        if actual != set(entries) | {'bundle-manifest.json'}: raise ValueError('Runtime closed inventory differs')
        for name, entry in entries.items():
            if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('Unsafe runtime member')
            p = runtime / name
            if p.stat().st_size != entry['bytes'] or file_sha(p) != entry['sha256']: raise ValueError('Runtime member changed: ' + name)
    if file_sha(code / 'tools/arc_next_offline_bundle.py') != VERIFIER_SHA:
        raise ValueError('Original verifier source changed')
    if file_sha(code / 'tools/arc_n1.py') != N1_SOURCE_SHA: raise ValueError('Original N1 source changed')
    for name, module in list(sys.modules.items()):
        if name == 'tools' or name.startswith('tools.'):
            locations = ([getattr(module, '__file__')] if getattr(module, '__file__', None) else list(getattr(module, '__path__', [])))
            if not locations or any(not Path(p).resolve().is_relative_to(code / 'tools') for p in locations):
                raise RuntimeError('Restart kernel: stale tools module from another runtime')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(code))
    if verify_all:
        from tools.arc_next_offline_bundle import verify_runtime
        verify_runtime(runtime, RUNTIME_MANIFEST_SHA)
    return code

def _validate_config(cfg):
    keys = {'runtime_root', 'model_root', 'wheels_root', 'interpreter_root', 'adapter_root',
            'output_root', 'interpreter_dir', 'environment_dir', 'pins'}
    if set(cfg) != keys or set(cfg['pins']) != {'runtime', 'model', 'wheels', 'interpreter', 'adapter'}:
        raise ValueError('Exactly five Dataset roots/pins and three output roots required')
    if cfg['pins']['runtime']['manifest_sha256'] != RUNTIME_MANIFEST_SHA: raise ValueError('Runtime8 required')
    inputs = [Path(cfg[role + '_root']).resolve() for role in cfg['pins']]
    for k in keys - {'pins'}:
        path = Path(cfg[k])
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Absolute non-symlink paths required')
    for key in ('output_root', 'interpreter_dir', 'environment_dir'):
        target = Path(cfg[key]).resolve()
        if any(target.is_relative_to(p) for p in inputs): raise ValueError('Outputs must remain outside all immutable inputs')
    for pin in cfg['pins'].values():
        if (pin.get('private') is not True or not re.fullmatch(r'[^/]+/[^/]+/[1-9][0-9]*', pin.get('reference', ''))
                or not re.fullmatch(r'[0-9a-f]{64}', pin.get('manifest_sha256', ''))):
            raise ValueError('Exact versioned private Dataset SHA pins required')
    return cfg

def _supervise(command, label, output, deadline, *, own_group=True):
    """Tail retained logs and emit heartbeat; stop immediately after terminal child status."""
    from tools.arc_n1 import stop_owned
    from tools.arc_next_offline_runtime import _refresh_owned_processes, _process_identity
    logpath = Path(output) / ('process-' + label + '.log')
    start = time.monotonic(); timedout = False; cancellation = None
    progress('process-start', process=label, seconds_remaining=max(0, round(deadline - start)))
    env = dict(os.environ, PYTHONUNBUFFERED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        HF_DATASETS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', WANDB_DISABLED='true', TOKENIZERS_PARALLELISM='false')
    owned = {}; offset = 0; last_heartbeat = start
    with logpath.open('xb') as log:
        p = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=own_group, env=env)
        try:
            ident = _process_identity(p.pid)
            if ident: owned[(ident['pid'], ident['birth'])] = ident
            while True:
                _refresh_owned_processes(p.pid, owned)
                with logpath.open('rb') as source:
                    source.seek(offset); new = source.read(); offset = source.tell()
                if new: print(new.decode('utf-8', errors='replace'), end='', flush=True)
                code = p.poll()
                if code is not None: break
                now = time.monotonic()
                if now >= deadline:
                    timedout = True; code = stop_owned(p, own_group=own_group, owned=owned); break
                if now - last_heartbeat >= 20:
                    progress('process-running', process=label, elapsed_seconds=round(now-start),
                             seconds_remaining=max(0, round(deadline-now)))
                    last_heartbeat = now
                time.sleep(.25)
            if _refresh_owned_processes(p.pid, owned):
                stop_owned(p, own_group=own_group, owned=owned); code = code or -1
        except BaseException as exc:
            code = stop_owned(p, own_group=own_group, owned=owned)
            cancellation = {'type': type(exc).__name__, 'message': str(exc)[:1000]}
        finally:
            if p.poll() is None: stop_owned(p, own_group=own_group, owned=owned)
    with logpath.open('rb') as source:
        source.seek(offset); new = source.read()
        if new: print(new.decode('utf-8', errors='replace'), end='', flush=True)
    result = {'process': label, 'returncode': code, 'timed_out': timedout, 'confirmed_stopped': p.poll() is not None,
              'cancellation': cancellation, 'wall_seconds_including_load': time.monotonic()-start}
    progress('process-finished', **result)
    return result

def render_messages(tokenizer, messages):
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    if type(text) is not str or not text: raise ValueError('Nonempty native chat template required')
    ids = tokenizer.encode(text, add_special_tokens=False)
    if type(ids) is not list or not ids or any(type(x) is not int or x < 0 for x in ids):
        raise ValueError('Exact token IDs required')
    return {'messages':messages,'messages_sha256':digest(messages),'rendered_text':text,
        'rendered_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'input_token_ids':ids,
        'input_token_ids_sha256':digest(ids),'prompt_tokens':len(ids),'enable_thinking':False,'truncation_applied':False}

def classify_grid(text):
    result = {'format_admitted':False,'python_parse_admitted':None,'ast_admitted':None,
        'demo_execution_success':None,'all_demonstrations_exact':None,'query_execution_success':None,
        'candidate':None,'program_steps':0,'verification_seconds':0.,'feedback':None,'error_category':'grid-json-invalid'}
    if type(text) is not str or len(text.encode()) > 65536: return {**result,'error_category':'response-size-limit'}
    try: candidate = grid(json.loads(text))
    except (ValueError,TypeError,RecursionError): return result
    return {**result,'format_admitted':True,'candidate':candidate,'error_category':None}

def select_candidates(rows):
    unique={}
    for row in rows:
        result=row['result']; candidate=result.get('candidate')
        if result.get('score_eligible') and candidate is not None:
            key=digest(candidate)
            if key not in unique: unique[key]={'grid':candidate,'votes':0,'first_call':row['identity']['call_index'],'digest':key}
            unique[key]['votes']+=1
    ranked=sorted(unique.values(),key=lambda x:(-x['votes'],x['first_call'],x['digest']))
    return {'policy':'vote_then_first-call_then-digest; two distinct grids','ranked':ranked,'selected':[r['grid'] for r in ranked[:2]]}

ROOT=Path(__file__).resolve().parent
ENGINEERING_TASKS=('68bc2e87','fafffa47','33067df9','996ec1f3','66e6c45b','c444b776','7ec998c9','b25e450b')
CONFIRMATION_SHA='1c9d0d71f0229a862b9f3f65d994cae3f44757165b4b88d78f7e46ec31a2bef6'
PREREQUISITES={'N9':('N6','host_toolbox'),'N10':('N6','host_toolbox'),'N11':('N6','host_toolbox'),'N12':('N7','typed_ir')}
ELIGIBLE_POLICIES={'N6':'host_toolbox','N7':'typed_ir','N9':'raw_plus_objects','N10':'true_demo','N11':'best_first_memory'}

def progress(event, **details):
    print('IRIS-SUITE '+canonical({'event':event,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**details}).decode(),flush=True)


def verify_sources():
    lock=read(ROOT/'source-lock.json')
    if lock.get('format')!='irisx/nextphase-source-lock-v1':raise ValueError('Source lock format')
    for name,expected in lock['files'].items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or len(p.parts)!=1 or (ROOT/p).is_symlink():raise ValueError('Unsafe source path')
        if file_sha(ROOT/p)!=expected:raise ValueError('Source pin differs: '+name)
    return lock


def component(name):
    if name=='arc_curriculum':
        dependency=component('arc_typed_ir')
        if 'arc_typed_ir' in sys.modules and sys.modules['arc_typed_ir'] is not dependency:raise ValueError('Stale typed IR module')
        sys.modules['arc_typed_ir']=dependency
    lock=verify_sources();filename=name+'.py';expected=lock['files'][filename];path=ROOT/filename
    source=path.read_bytes()
    if hashlib.sha256(source).hexdigest()!=expected:raise ValueError('Captured component source differs from pin')
    module_name='irisx_suite_'+name+'_'+expected
    if module_name not in sys.modules:
        class VerifiedLoader(importlib.machinery.SourceFileLoader):
            def get_code(self,fullname):return self.source_to_code(source,str(path))
        spec=importlib.util.spec_from_file_location(module_name,path,loader=VerifiedLoader(module_name,str(path)))
        module=importlib.util.module_from_spec(spec);sys.modules[module_name]=module;spec.loader.exec_module(module)
        module._bound_sha=expected
    module=sys.modules[module_name]
    if getattr(module,'_bound_sha',None)!=expected or Path(module.__file__).resolve()!=path:raise ValueError('Stale component')
    return module


def design():return read(ROOT/'DESIGN-FROZEN.json')
def spec_for(run_id):
    found=[x for x in design()['runs'] if x['id']==run_id]
    if len(found)!=1:raise ValueError('Exact N5..N14 run required')
    return found[0]


def seed_for(tid,slot):return int(digest(['irisx-nextphase-paired-v1',tid,1015])[:8],16)%(2**31-8)+slot


def condition_order(core):
    return [(t,a) for t in sorted(core['tasks'],key=lambda t:digest(['suite-task-v1',1015,t]))
            for a in sorted(core['record_arms'],key=lambda a:digest(['suite-arm-v1',core['run_id'],t,a]))]


def identities(core):
    records=[];core_sha=digest(core)
    if core['run_id']=='N5':
        payload=read(ROOT/'n4-replay-payload.json')
        for arm in core['record_arms']:
            for i,row in enumerate(payload['records']):
                identity={'core_sha256':core_sha,'task_id':row['task_id'],'arm':arm,'call_index':i,
                          'original_record_id':row['record_id'],'seed':None,'weight':'no_model'}
                identity['condition_id']=digest([core_sha,row['task_id'],arm]);identity['record_id']=digest(identity);records.append(identity)
    else:
        for tid,arm in condition_order(core):
            for slot in range(4):
                identity={'core_sha256':core_sha,'task_id':tid,'arm':arm,'call_index':slot,'seed':seed_for(tid,slot),'weight':'base'}
                identity['condition_id']=digest([core_sha,tid,arm]);identity['record_id']=digest(identity);records.append(identity)
    return records


def make_manifest(run_id,original,challenges,*,selected_policy=None,gate_receipts=None):
    spec=spec_for(run_id);old=original['core'];lock=verify_sources()
    tasks=list(old['tuning_ids'][8:40]) if run_id=='N14' else list(ENGINEERING_TASKS)
    if old['tuning_ids'][:8]!=list(ENGINEERING_TASKS) or len(old['confirmation_ids'])!=136 or digest(old['confirmation_ids'])!=CONFIRMATION_SHA:
        raise ValueError('Frozen exposure inventory changed')
    if set(tasks)&set(old['confirmation_ids']) or len(tasks)!=spec['tasks']:raise ValueError('Protected task or task count')
    for tid in tasks:
        task(challenges[tid])
        if digest(challenges[tid])!=original['challenge_sha256'][tid]:raise ValueError('Visible task binding changed')
    if run_id=='N14' and selected_policy not in ELIGIBLE_POLICIES.values():raise ValueError('N14 selected policy invalid')
    record_arms=['proposal_pool'] if run_id=='N12' else spec['arms']
    policies={a:(selected_policy if a=='selected_agent' else a) for a in record_arms}
    core={'format':'irisx/nextphase-core-v1','run_id':run_id,'experiment_id':'iris-x-'+run_id.lower()+'-20261009',
          'spec':spec,'tasks':tasks,'record_arms':record_arms,'score_arms':spec['arms'],'policies':policies,
          'slots_per_condition':4,'source_lock':lock,'source_lock_sha256':file_sha(ROOT/'source-lock.json'),
          'design_sha256':file_sha(ROOT/'DESIGN-FROZEN.json'),'pins':EXPECTED_PINS,
          'challenge_sha256':{t:original['challenge_sha256'][t] for t in tasks},
          'solutions_sha256':old['solutions_sha256'],'base_manifest_sha256':old['base_manifest_sha256'],
          'adapter_binding_sha256':old['adapter_binding_sha256'],'source_n1_core_sha256':original['core_sha256'],
          'confirmation_ids':old['confirmation_ids'],'confirmation_ids_sha256':CONFIRMATION_SHA,'confirmation_used':False,
          'gate_receipts':gate_receipts or [],'max_new_tokens':MAX_NEW,'max_prompt_tokens':MAX_PROMPT,'max_context_tokens':MAX_CONTEXT,
          'sampling':SAMPLING,'max_generate_calls':spec['max_model_calls'],'max_generated_tokens':spec['max_model_calls']*MAX_NEW,
          'max_prompt_tokens':MAX_PROMPT,'max_prompt_tokens_total':spec['max_model_calls']*MAX_PROMPT,
          'training_performed':False,'adapter_used':False,'resumption_permitted':False,'official_score':None}
    return {'format':'irisx/nextphase-manifest-v1','core':core,'core_sha256':digest(core),'records':identities(core)}


def verify_manifest(manifest,challenges):
    core=manifest['core'];spec=spec_for(core['run_id'])
    if manifest['format']!='irisx/nextphase-manifest-v1' or digest(core)!=manifest['core_sha256']:raise ValueError('Manifest digest')
    if core['spec']!=spec or core['source_lock']!=verify_sources() or core['source_lock_sha256']!=file_sha(ROOT/'source-lock.json'):
        raise ValueError('Manifest source/design mismatch')
    if core['pins']!=EXPECTED_PINS or core['design_sha256']!=file_sha(ROOT/'DESIGN-FROZEN.json'):raise ValueError('Exact pins required')
    if core['max_generate_calls']!=spec['max_model_calls'] or manifest['records']!=identities(core):raise ValueError('Manifest identities/budget')
    if digest(core['confirmation_ids'])!=CONFIRMATION_SHA or core['confirmation_used'] is not False:raise ValueError('Protected confirmation changed')
    if set(challenges)!=set(core['tasks']) or set(challenges)&set(core['confirmation_ids']):raise ValueError('Task inventory')
    for tid,value in challenges.items():
        task(value)
        if digest(value)!=core['challenge_sha256'][tid]:raise ValueError('Challenge hash')
    original=read(ROOT/'solver-manifest-reference.json')
    selected=core['policies'].get('selected_agent') if core['run_id']=='N14' else None
    expected=make_manifest(core['run_id'],original,challenges,selected_policy=selected,gate_receipts=core.get('gate_receipts'))
    if manifest!=expected:raise ValueError('Frozen experiment contract changed, even if rehashed')
    return core


def _evidence_inventory(output):
    output=Path(output)
    if any(p.is_symlink() for p in output.rglob('*')):raise ValueError('Symlink evidence forbidden')
    return {p.relative_to(output).as_posix():file_sha(p) for p in sorted(output.rglob('*')) if p.is_file()}


def seal(output,manifest,dispatch):
    output=Path(output)
    if dispatch.get('confirmed_stopped') is not True:raise ValueError('Cannot seal live workers')
    allowed={r['record_id'] for r in manifest['records']};root=output/'records'
    if root.exists() and any(not p.is_dir() or p.name not in allowed for p in root.iterdir()):raise ValueError('Unexpected record identity')
    states={'completed':[],'excluded':[],'unknown':[],'verification_incomplete':[],'missing':[]}
    for rec in manifest['records']:
        folder=root/rec['record_id']
        if (folder/'result.json').is_file():state='completed' if read(folder/'result.json')['status']=='completed' else 'excluded'
        elif (folder/'response.json').is_file():state='verification_incomplete'
        elif (folder/'attempted.json').is_file():state='unknown'
        else:state='missing'
        states[state].append(rec['record_id'])
    value={'format':'irisx/nextphase-seal-v1','core_sha256':manifest['core_sha256'],'files':_evidence_inventory(output),
           'states':states,'expected_count':len(manifest['records']),'confirmed_stopped':True,'dispatch':dispatch}
    write(output/'seal.json',value);return value


def check_seal(output,manifest,*,postscore=False):
    output=Path(output);sealed=read(output/'seal.json')
    if sealed['core_sha256']!=manifest['core_sha256'] or sealed['confirmed_stopped'] is not True:raise ValueError('Stopped matching seal required')
    suffix={'seal.json'}|({'report.json','summary.json','final-inventory.json'} if postscore else set())
    actual=_evidence_inventory(output)
    if set(actual)!=set(sealed['files'])|suffix:raise ValueError('Evidence closed inventory changed')
    if any(actual[k]!=v for k,v in sealed['files'].items()):raise ValueError('Evidence bytes changed')
    return sealed


def verified_prior(path,run_id):
    """Read owner-supplied artifact integrity; this is not signature authentication."""
    path=materialize_prior(path);verify_final_inventory(path);manifest=read(path/'manifest.json');core=verify_manifest(manifest,read(path/'challenges.json'))
    if core['run_id']!=run_id:raise ValueError('Wrong prerequisite run')
    sealed=check_seal(path,manifest,postscore=True);summary=read(path/'summary.json');report=read(path/'report.json')
    if summary['status']!='complete' or sealed['states']['missing'] or sealed['states']['unknown'] or sealed['states']['verification_incomplete']:
        raise ValueError('Prerequisite requires closed complete ledger, no missing/unknown')
    if not summary['processes_ok']:raise ValueError('Prerequisite process stop invalid')
    if report['core_sha256']!=manifest['core_sha256'] or report['confirmation_used'] is not False:raise ValueError('Prerequisite report binding')
    return manifest,report,{'run_id':run_id,'core_sha256':manifest['core_sha256'],'report_sha256':file_sha(path/'report.json'),
                            'seal_sha256':file_sha(path/'seal.json'),'summary_sha256':file_sha(path/'summary.json')}


def resolve_gate(run_id,prior_paths):
    receipts=[]
    if run_id in PREREQUISITES:
        required,arm=PREREQUISITES[run_id]
        if required not in prior_paths:return {'status':'blocked','reason':'missing-prerequisite','required':required,'arm':arm}
        _,report,receipt=verified_prior(prior_paths[required],required);group=report['groups'][arm]
        if group['stages']['ast_admitted']<8 or group['stages']['demo_execution_success']<4:
            return {'status':'blocked','reason':'admission-threshold-not-met','required':required,'arm':arm,'receipt':receipt}
        receipts.append(receipt)
    if run_id=='N14':
        candidates=[]
        for required,arm in ELIGIBLE_POLICIES.items():
            if required not in prior_paths:return {'status':'blocked','reason':'missing-consolidation-source','required':required}
            path=materialize_prior(prior_paths[required]);verify_final_inventory(path)
            if (path/'blocked.json').is_file():
                blocked=read(path/'blocked.json')
                if blocked.get('run_id')!=required or blocked.get('source_lock_sha256')!=file_sha(ROOT/'source-lock.json') or blocked.get('status')!='blocked':
                    raise ValueError('Invalid prerequisite-BLOCKED receipt')
                # Only N9/N10/N11 can be transitively blocked by the admission gate.
                if required not in ('N9','N10','N11') or blocked.get('reason')!='admission-threshold-not-met':
                    raise ValueError('Incomplete/missing-source receipt cannot waive consolidation evidence')
                base_path=prior_paths.get('N6')
                if not base_path:raise ValueError('Blocked receipt must revalidate N6')
                _,base_report,base_receipt=verified_prior(base_path,'N6');g=base_report['groups']['host_toolbox']
                if g['stages']['ast_admitted']>=8 and g['stages']['demo_execution_success']>=4:raise ValueError('False blocked receipt')
                if blocked.get('receipt')!=base_receipt:raise ValueError('Blocked lineage mismatch')
                receipts.append({'run_id':required,'blocked_sha256':file_sha(path/'blocked.json')});continue
            _,report,receipt=verified_prior(path,required);receipts.append(receipt);group=report['groups'][arm]
            if group['top2_exact']>=1 and group['stages']['ast_admitted']>=8 and group['stages']['demo_execution_success']>=4:
                candidates.append({'policy':arm,'top2':group['top2_exact'],'top1':group['top1_exact'],
                                   'generated_tokens':group['known_generated_tokens'],'source':required})
        if not candidates:return {'status':'blocked','reason':'no-qualifying-agent-policy','receipts':receipts}
        chosen=sorted(candidates,key=lambda x:(-x['top2'],-x['top1'],x['generated_tokens'],x['policy']))[0]
        return {'status':'passed','selected_policy':chosen['policy'],'selection':chosen,'receipts':receipts,
                'interpretation':'best among tested qualifying policies on exposed engineering8; N14 is disjoint but previously N3-exposed'}
    return {'status':'passed','receipts':receipts}


def render_initial(value,policy,tokenizer):
    p=component('arc_suite_policy');v=component('arc_program_v2');ir=component('arc_typed_ir')
    return render_messages(tokenizer,p.initial_messages(value,policy,detailed_contract=v.program_contract,ir_contract=ir.plan_contract))


def verify_candidate(text,value,policy):
    if policy=='direct_grid':return classify_grid(text)
    v=component('arc_program_v2');source=text;ir=None
    if policy in ('typed_ir','proposal_pool'):
        try:
            module=component('arc_typed_ir');ir=module.parse_plan(text);source=module.compile_plan(ir)
        except (ValueError,TypeError,KeyError,RecursionError) as exc:
            result=v._result();result.update(error_category='typed_ir',feedback={'error':str(exc)[:512],'demonstrations':[],'all_demonstrations_exact':False})
            return result
    if policy=='proposal_pool':
        result=v._result();result.update(format_admitted=True,typed_plan=ir,program_steps=0,error_category=None,
            parse_only_prior_proposal=True,compiled_source_sha256=hashlib.sha256(source.encode()).hexdigest())
        return result
    result=v.verify_program(source,value,str(ROOT/'arc_bounded_v2.py'))
    result['compiled_source_sha256']=hashlib.sha256(source.encode()).hexdigest()
    if ir is not None:result['typed_plan']=ir
    result['source_metadata']=component('arc_suite_policy').source_metadata(source)
    return result


def run_records(manifest,challenges,output,tokenizer,generate,model_id,deadline):
    core=verify_manifest(manifest,challenges);p=component('arc_suite_policy');audit=read(ROOT/'visible-token-audit.json')
    for tid,arm in condition_order(core):
        policy=core['policies'][arm];initial=render_initial(challenges[tid],policy,tokenizer)['messages'];archive=[];stop=None;gas=0
        for rec in [r for r in manifest['records'] if r['task_id']==tid and r['arm']==arm]:
            if time.monotonic()>=deadline:return
            folder=Path(output)/'records'/rec['record_id'];folder.mkdir(parents=True,exist_ok=False);write(folder/'identity.json',rec)
            if stop:
                write(folder/'result.json',{'status':stop,'generate_calls':0,'score_eligible':False,'candidate':None,'program_steps':0});continue
            try:
                messages,parent=p.next_messages(initial,policy,archive)
            except ValueError:
                stop='repair-size-excluded';write(folder/'result.json',{'status':stop,'generate_calls':0,'score_eligible':False,'candidate':None,'program_steps':0});continue
            progress('record-render',run=core['run_id'],task=tid,arm=arm,slot=rec['call_index'])
            record_deadline=min(deadline,time.monotonic()+120)
            rendered=render_messages(tokenizer,messages);write(folder/'prompt.json',rendered)
            if messages==initial:
                expected=audit['prompts'][tid][policy]
                if any(rendered[k]!=expected[k] for k in ('prompt_tokens','input_token_ids_sha256','rendered_text_sha256')):raise ValueError('Pinned initial prompt differs from audit')
            if rendered['prompt_tokens']>MAX_PROMPT:
                stop='context-excluded';write(folder/'result.json',{'status':stop,'generate_calls':0,'score_eligible':False,'candidate':None,'program_steps':0,'prompt_tokens':rendered['prompt_tokens']});continue
            if time.monotonic()>=record_deadline:
                write(folder/'result.json',{'status':'deadline-before-call','generate_calls':0,'score_eligible':False,'candidate':None,'program_steps':0});return
            request={'record_id':rec['record_id'],'seed':rec['seed'],'input_token_ids':rendered['input_token_ids'],
                     'max_new_tokens':MAX_NEW,'deadline_monotonic':record_deadline,'model_id':model_id,'sampling':SAMPLING,
                     'repair_parent_record_id':parent}
            write(folder/'request.json',request);write(folder/'attempted.json',{'model_id':model_id,'seed':rec['seed'],'prompt_tokens':rendered['prompt_tokens'],'max_new_tokens':MAX_NEW})
            started=time.monotonic();response=generate(request)
            if (type(response) is not dict or type(response.get('text')) is not str or response.get('model_id')!=model_id or
                type(response.get('generated_tokens')) is not int or not 0<=response['generated_tokens']<=MAX_NEW or
                response.get('prompt_tokens')!=rendered['prompt_tokens'] or response.get('finish_reason') not in ('stop','length','wall')):
                raise ValueError('Generation usage/model contract violated')
            write(folder/'response.json',response);generation_seconds=time.monotonic()-started
            verification=verify_candidate(response['text'],challenges[tid],policy);gas+=verification.get('program_steps',0)
            if gas>800000:raise ValueError('Per task-arm gas cap exceeded')
            late=response['finish_reason']=='wall' or time.monotonic()>=record_deadline
            result={**verification,'status':'late-response' if late else 'completed','generate_calls':1,
                    'score_eligible':not late and verification.get('candidate') is not None,
                    'prompt_tokens':response['prompt_tokens'],'generated_tokens':response['generated_tokens'],
                    'generation_seconds':generation_seconds,'finish_reason':response['finish_reason'],
                    'repair_parent_record_id':parent,'cumulative_program_steps':gas,'response_sha256':digest(response['text'])}
            write(folder/'result.json',result);archive.append({'identity':rec,'response':response,'result':result})
            progress('record-complete',run=core['run_id'],task=tid,arm=arm,slot=rec['call_index'],tokens=response['generated_tokens'],
                     ast=result.get('ast_admitted'),demo_fit=result.get('all_demonstrations_exact'),status=result['status'])
            if late:stop='condition-stopped-after-late-response'
        write(Path(output)/'conditions'/digest([manifest['core_sha256'],tid,arm])/'selection.json',{'task_id':tid,'arm':arm,**select_candidates(archive)})
    if core['run_id']=='N12':run_synthesis(manifest,challenges,output,deadline)


def run_synthesis(manifest,challenges,output,deadline):
    ir=component('arc_typed_ir');v=component('arc_program_v2');core=manifest['core'];output=Path(output)
    for tid in core['tasks']:
        proposals=[]
        for rec in manifest['records']:
            if rec['task_id']!=tid:continue
            f=output/'records'/rec['record_id']/'result.json'
            if f.exists():
                r=read(f)
                if r.get('status')=='completed' and r.get('typed_plan') is not None:proposals.append(r['typed_plan'])
        for arm in sorted(core['score_arms'],key=lambda a:digest(['synthesis-arm',tid,a])):
            if time.monotonic()>=deadline:return
            started=time.monotonic();cpu_deadline=min(deadline,started+30);ranked=ir.order_candidates(proposals,mode=arm,alpha=1.0)
            search_root=output/'search'/tid/arm
            write(search_root/'metadata.json',{'task_id':tid,'arm':arm,'expansion_denominator':64,'prior_support_count':len(ranked),
                                              'grammar_manifest':ir.grammar_manifest(),'deadline_seconds':30})
            rows=[];gas=0;stop='expansion-cap'
            for i in range(64):
                identity={'task_id':tid,'arm':arm,'call_index':i,'record_id':digest([manifest['core_sha256'],tid,arm,i]),'weight':'no_model'}
                folder=search_root/'slots'/str(i);write(folder/'identity.json',identity)
                if i>=len(ranked):
                    result={'status':'prior-support-excluded','score_eligible':False,'candidate':None,'program_steps':0}
                elif time.monotonic()>=cpu_deadline:
                    result={'status':'cpu-deadline-excluded','score_eligible':False,'candidate':None,'program_steps':0};stop='cpu-deadline'
                else:
                    candidate=ranked[i]
                    write(folder/'attempted.json',{'candidate_id':candidate['id'],'program_sha256':hashlib.sha256(candidate['program'].encode()).hexdigest(),
                                                  'reserved_program_steps':200000,'timeout_seconds':min(3,max(.001,cpu_deadline-time.monotonic()))})
                    receipt=v.verify_program(candidate['program'],challenges[tid],str(ROOT/'arc_bounded_v2.py'),
                                             timeout_seconds=min(3,max(.001,cpu_deadline-time.monotonic())))
                    gas+=receipt['program_steps'];late=time.monotonic()>=cpu_deadline
                    result={**receipt,'status':'late-response' if late else 'completed','score_eligible':not late and receipt.get('candidate') is not None,
                            'grammar_candidate_id':candidate['id'],'prior_weight':candidate['prior_weight'],'production_ids':candidate['production_ids']}
                write(folder/'result.json',result);rows.append({'identity':identity,'result':result})
            if gas>64*200000:raise ValueError('Synthesis gas budget exceeded')
            write(search_root/'complete.json',{'program_steps':gas,'wall_seconds':time.monotonic()-started,'stop_reason':stop,'selection':select_candidates(rows)})
            progress('search-arm-complete',task=tid,arm=arm,attempted=sum(r['result']['status'] in ('completed','late-response') for r in rows),steps=gas)


def run_replay(manifest,challenges,output,deadline):
    payload=read(ROOT/'n4-replay-payload.json');byid={r['record_id']:r for r in payload['records']};output=Path(output)
    if len(byid)!=61 or payload['query_gold_included'] is not False or payload['query_exact_labels_included'] is not False:
        raise ValueError('Truth-free fixed61 replay inventory differs')
    verifiers={'immutable_n4':component('arc_n4_program'),'bounded_v2':component('arc_program_v2')}
    agents={'immutable_n4':ROOT/'arc_bounded_v1.py','bounded_v2':ROOT/'arc_bounded_v2.py'}
    for rec in manifest['records']:
        if time.monotonic()>=deadline:return
        original=byid[rec['original_record_id']];source=original['source']
        if hashlib.sha256(source.encode()).hexdigest()!=original['source_sha256_utf8'] or digest(source)!=original['response_sha256_canonical_string']:
            raise ValueError('Original response source changed')
        if digest(challenges[rec['task_id']])!=original['visible_challenge_sha256']:raise ValueError('Replay task mismatch')
        folder=output/'records'/rec['record_id'];folder.mkdir(parents=True,exist_ok=False);write(folder/'identity.json',rec)
        write(folder/'replay-input.json',{'original_record_id':original['record_id'],'source':source,'source_sha256':original['source_sha256_utf8']})
        write(folder/'attempted.json',{'kind':'cpu-verification','model_calls':0,'reserved_program_steps':200000})
        result=verifiers[rec['arm']].verify_program(source,challenges[rec['task_id']],str(agents[rec['arm']]),timeout_seconds=min(3,max(.001,deadline-time.monotonic())))
        late=time.monotonic()>=deadline
        write(folder/'result.json',{**result,'status':'late-response' if late else 'completed','score_eligible':not late and result.get('candidate') is not None,
                                   'generate_calls':0,'original_record_id':original['record_id']})
        progress('replay-record-complete',arm=rec['arm'],original_record_id=original['record_id'],ast=result['ast_admitted'],demo_fit=result['all_demonstrations_exact'])


def worker(request):
    _runtime_tools(request['runtime_root'],verify_all=True)
    from tools.arc_next_models import load_candidate,observe_g4_hardware
    import torch
    manifest,challenges=read(request['manifest_path']),read(request['challenges_path']);core=verify_manifest(manifest,challenges)
    output=Path(request['output']);block=output/'block-base';block.mkdir(exist_ok=False)
    write(block/'hardware.json',observe_g4_hardware(torch))
    if file_sha(request['model_manifest_path'])!=core['base_manifest_sha256']:raise ValueError('Base material pin')
    progress('model-loading',run=core['run_id'],weight='base')
    session=load_candidate(request['model_path'],manifest_path=request['model_manifest_path'],environment_lock_path=request['environment_lock_path'],adapter_path=None)
    session.model.eval();model_id='sha256:'+digest(session.identity);write(block/'identity.json',session.identity)
    write(block/'fresh-load-check.json',{'status':'passed','pid':os.getpid(),'weight':'base','adapter_loaded':False,'probe_generate_calls':0})
    progress('model-ready',run=core['run_id'],model_id=model_id)
    from transformers import StoppingCriteria,StoppingCriteriaList
    class Deadline(StoppingCriteria):
        def __init__(self,value):self.value=value
        def __call__(self,input_ids,scores,**kwargs):return time.monotonic()>=self.value
    def generate(req):
        if time.monotonic()>=req['deadline_monotonic']:raise TimeoutError('Deadline before generation')
        ids=torch.tensor([req['input_token_ids']],dtype=torch.long,device=session.model.device)
        torch.manual_seed(req['seed']);torch.cuda.manual_seed_all(req['seed']);torch.cuda.reset_peak_memory_stats();started=time.monotonic()
        with torch.inference_mode():
            outputs=session.model.generate(input_ids=ids,attention_mask=torch.ones_like(ids),max_new_tokens=MAX_NEW,
                do_sample=True,temperature=.7,top_p=.95,use_cache=True,return_dict_in_generate=False,
                stopping_criteria=StoppingCriteriaList([Deadline(req['deadline_monotonic'])]),
                pad_token_id=session.tokenizer.pad_token_id if session.tokenizer.pad_token_id is not None else session.tokenizer.eos_token_id)
        generated=outputs[0,ids.shape[-1]:];torch.cuda.synchronize();count=int(generated.numel())
        return {'text':session.tokenizer.decode(generated,skip_special_tokens=True),'model_id':model_id,
                'prompt_tokens':int(ids.shape[-1]),'generated_tokens':count,'output_token_ids':generated.tolist(),
                'finish_reason':'wall' if time.monotonic()>=req['deadline_monotonic'] else 'length' if count==MAX_NEW else 'stop',
                'generation_wall_seconds':time.monotonic()-started,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                'peak_reserved_bytes':torch.cuda.max_memory_reserved()}
    run_records(manifest,challenges,output,session.tokenizer,generate,model_id,request['deadline'])
    write(block/'complete.json',{'completed':True,'weight':'base','pid':os.getpid()})


def controller(request):
    cfg,output,deadline=request['config'],Path(request['output']),request['deadline'];run_id=request['run_id']
    _runtime_tools(cfg['runtime_root'],verify_all=True)
    from tools.arc_next_offline_runtime import launch_phase,_runtime_environment
    from tools.arc_next_offline_environment import install_offline
    from tools.arc_n1 import verify_adapter
    legacy={k:v for k,v in cfg.items() if k!='adapter_root'};legacy['pins']={k:v for k,v in cfg['pins'].items() if k!='adapter'}
    legacy.update(training_profile='pilot128',enable_training_pilot=False,max_wall_seconds=request['watchdog_seconds'],adapter_path=None,run_tag='iris-x-'+run_id.lower()+'-20261009')
    progress('verify-offline-inputs',run=run_id);launch_phase('VERIFY_OFFLINE_INPUTS',legacy,enabled=True)
    environment=Path(cfg['environment_dir'])
    if not environment.exists():install_offline(Path(cfg['runtime_root'])/'runtime/research/arc-next-line/model-source-lock.json',cfg['wheels_root'],environment,enabled=True)
    installed=_runtime_environment(legacy);write(output/'environment.json',installed)
    write(output/'cpu-check.json',launch_phase('CHECK_CPU_IMPORTS',legacy,enabled=True))
    adapter=Path(cfg['adapter_root']);manifest=read(output/'manifest.json')
    if file_sha(adapter/'adapter-manifest.json')!=cfg['pins']['adapter']['manifest_sha256']:raise ValueError('Adapter Dataset pin')
    verify_adapter(adapter/'adapter',manifest['core']['adapter_binding_sha256'])
    path=output/'worker-base.json';write(path,{'runtime_root':cfg['runtime_root'],'manifest_path':str(output/'manifest.json'),
        'challenges_path':str(output/'challenges.json'),'output':str(output),'deadline':deadline-30,'model_path':cfg['model_root'],
        'model_manifest_path':str(Path(cfg['model_root'])/'irisx-model-material.json'),'environment_lock_path':installed['environment_lock']})
    result=_supervise(installed['python_command']+[str(ROOT/'arc_suite.py'),'worker',str(path)],'base',output,deadline-30,own_group=False)
    write(output/'blocks.json',[result])


def _load_rows(manifest,output):
    output=Path(output);rows=[]
    for rec in manifest['records']:
        folder=output/'records'/rec['record_id'];resultpath=folder/'result.json'
        result=read(resultpath) if resultpath.is_file() else {'status':'verification-incomplete' if (folder/'response.json').is_file() else 'unknown-usage' if (folder/'attempted.json').is_file() else 'missing','candidate':None,'score_eligible':False}
        cpu_attempted=rec['weight']=='no_model' and (folder/'attempted.json').is_file()
        if cpu_attempted and not resultpath.is_file():
            result={'status':'cpu-work-unknown','candidate':None,'score_eligible':False,'program_steps':200000}
        response=read(folder/'response.json') if (folder/'response.json').is_file() else None
        replay=read(folder/'replay-input.json')['source'] if (folder/'replay-input.json').is_file() else None
        rows.append({'identity':rec,'result':result,'response':response,'replay_source':replay,'cpu_attempted':cpu_attempted,'attempted':(folder/'attempted.json').is_file()})
    return rows


def _group_stats(rows,task_count,slot_denominator,*,model_rows=None):
    stages=('format_admitted','python_parse_admitted','ast_admitted','demo_execution_success','all_demonstrations_exact','query_execution_success')
    model_rows=rows if model_rows is None else model_rows
    result={'task_denominator':task_count,'slot_denominator':slot_denominator,'completed_slots':sum(x['result']['status']=='completed' for x in rows),
            'missing_slots':sum(x['result']['status']=='missing' for x in rows),'unknown_slots':sum(x['result']['status'] in ('unknown-usage','cpu-work-unknown') for x in rows),
            'verification_incomplete_slots':sum(x['result']['status']=='verification-incomplete' for x in rows),
            'cpu_verification_reservations':sum(x.get('cpu_attempted',False) for x in rows),
            'cpu_unknown_work_reservations':sum(x['result']['status']=='cpu-work-unknown' for x in rows),
            'excluded_slots':sum(x['result']['status'] not in ('completed','missing','unknown-usage','cpu-work-unknown','verification-incomplete') for x in rows),
            'eligible_slots':sum(bool(x['result'].get('score_eligible')) for x in rows),'stages':{s:sum(x['result'].get(s) is True for x in rows) for s in stages},
            'stages_assessed':{s:sum(x['result'].get(s) is not None for x in rows) for s in stages},'categories':{},
            'known_generate_calls':sum(x.get('response') is not None for x in model_rows),
            'call_reservations':sum(x.get('attempted',False) and x['identity']['weight']!='no_model' for x in model_rows),
            'known_prompt_tokens':sum((x.get('response') or {}).get('prompt_tokens',0) for x in model_rows),
            'known_generated_tokens':sum((x.get('response') or {}).get('generated_tokens',0) for x in model_rows),
            'cap_hits':sum((x.get('response') or {}).get('generated_tokens')==MAX_NEW for x in model_rows),
            'generation_seconds':sum((x.get('response') or {}).get('generation_wall_seconds',0) for x in model_rows),
            'verification_seconds':sum(x['result'].get('verification_seconds',0) for x in rows),
            'program_steps':sum(x['result'].get('program_steps',0) for x in rows),
            'program_steps_semantics':'charged gas: known steps plus conservative full-cap reservation when CPU usage is unknown',
            'top1_exact':0,'top2_exact':0,'oracle_any_eligible_exact':0,'first_top1_exact':0,'repair_attempts':0,'failed_to_ast':0,'failed_to_demo_fit':0,
            'unique_source_count':0,'bounded_feedback_signature_count':0}
    for row in rows:
        category=row['result'].get('error_category') or row['result']['status'];result['categories'][category]=result['categories'].get(category,0)+1
    return result


def score(output,manifest,solutions_path):
    """Only this post-stop evaluator reads query gold. No labels returned to solver."""
    output=Path(output);sealed=check_seal(output,manifest);core=verify_manifest(manifest,read(output/'challenges.json'));rows=_load_rows(manifest,output)
    if file_sha(solutions_path)!=core['solutions_sha256']:raise ValueError('Gold binding changed')
    truth=read(solutions_path)
    all_by_arm={a:[x for x in rows if x['identity']['arm']==a] for a in core['score_arms']};search_complete=True
    if core['run_id']=='N12':
        all_by_arm={a:[] for a in core['score_arms']}
        for tid in core['tasks']:
            for arm in core['score_arms']:
                search_root=output/'search'/tid/arm
                for i in range(64):
                    folder=search_root/'slots'/str(i);attempted=(folder/'attempted.json').is_file()
                    identity={'task_id':tid,'arm':arm,'call_index':i,'record_id':digest([manifest['core_sha256'],tid,arm,i]),'weight':'no_model'}
                    if (folder/'identity.json').is_file() and read(folder/'identity.json')!=identity:raise ValueError('Search identity mismatch')
                    if (folder/'result.json').is_file():result=read(folder/'result.json')
                    elif attempted:
                        search_complete=False;result={'status':'cpu-work-unknown','score_eligible':False,'candidate':None,'program_steps':200000}
                    else:
                        search_complete=False;result={'status':'missing','score_eligible':False,'candidate':None,'program_steps':0}
                    all_by_arm[arm].append({'identity':identity,'result':result,'cpu_attempted':attempted})
    groups={a:_group_stats(rs,len(core['tasks']),61 if core['run_id']=='N5' else 64*len(core['tasks']) if core['run_id']=='N12' else 4*len(core['tasks']),
                          model_rows=rows if core['run_id']=='N12' else None) for a,rs in all_by_arm.items()}
    tasks=[];record_lookup={x['identity'].get('record_id'):x for x in rows}
    for tid in core['tasks']:
        item={'task_id':tid,'arms':{}}
        for arm,arm_rows in all_by_arm.items():
            task_rows=[x for x in arm_rows if x['identity']['task_id']==tid];selected=select_candidates(task_rows);gold=truth[tid][0];first=task_rows[0]['result']
            stats={'top1_exact':bool(selected['selected'] and selected['selected'][0]==gold),'top2_exact':gold in selected['selected'],
                   'oracle_any_eligible_exact':any(x['grid']==gold for x in selected['ranked']),
                   'first_top1_exact':bool(first.get('score_eligible') and first.get('candidate')==gold),'selected_count':len(selected['selected'])}
            for key in ('top1_exact','top2_exact','oracle_any_eligible_exact','first_top1_exact'):groups[arm][key]+=int(stats[key])
            sources=[r['response']['text'] if r.get('response') is not None else r.get('replay_source') for r in task_rows]
            stats['unique_source_count']=len({digest(source) for source in sources if source is not None})
            stats['bounded_feedback_signature_count']=len({digest(r['result']['feedback']['demonstrations']) for r in task_rows if r['result'].get('feedback') is not None})
            stats['independent_root_count']=sum(r.get('response') is not None and not r['result'].get('repair_parent_record_id') for r in task_rows)
            stats['independent_root_scope']='new model-generation roots in this condition; CPU replay/search do not add model roots'
            stats['feedback_signature_interpretation']='lossy bounded feedback summary, not exact semantic equivalence; no pruning on it'
            item['arms'][arm]=stats
        tasks.append(item)
    for arm,arm_rows in all_by_arm.items():
        g=groups[arm];g['final_minus_first_top1']=g['top1_exact']-g['first_top1_exact']
        g['unique_source_count']=len({digest(r['response']['text'] if r.get('response') is not None else r['replay_source']) for r in arm_rows if r.get('response') is not None or r.get('replay_source') is not None})
        g['bounded_feedback_signature_count']=len({digest(r['result']['feedback']['demonstrations']) for r in arm_rows if r['result'].get('feedback') is not None})
        for row in arm_rows:
            parent=row['result'].get('repair_parent_record_id')
            if not parent:continue
            if parent not in record_lookup:raise ValueError('Repair parent absent')
            old=record_lookup[parent]
            if old['identity']['task_id']!=row['identity']['task_id'] or old['identity']['arm']!=arm or old['identity']['call_index']>=row['identity']['call_index']:
                raise ValueError('Repair parent crosses condition or time')
            g['repair_attempts']+=int(row['result'].get('generate_calls',0)>0)
            g['failed_to_ast']+=int(not old['result'].get('ast_admitted') and row['result'].get('ast_admitted') is True)
            g['failed_to_demo_fit']+=int(not old['result'].get('all_demonstrations_exact') and row['result'].get('all_demonstrations_exact') is True)
    physical={'call_reservations':sum(r['attempted'] and r['identity']['weight']!='no_model' for r in rows),
              'known_generate_calls':sum(r['response'] is not None for r in rows),
              'unknown_usage':sum(r['attempted'] and r['response'] is None and r['identity']['weight']!='no_model' for r in rows),
              'prompt_tokens':sum((r['response'] or {}).get('prompt_tokens',0) for r in rows),
              'generated_tokens':sum((r['response'] or {}).get('generated_tokens',0) for r in rows)}
    if physical['call_reservations']>core['max_generate_calls'] or physical['generated_tokens']>core['max_generate_calls']*MAX_NEW or physical['prompt_tokens']>core['max_generate_calls']*MAX_PROMPT:raise ValueError('Frozen model budget exceeded')
    reproducibility=[]
    if core['run_id'] in ('N8','N10','N11'):
        for tid in core['tasks']:
            initial=[next(r for r in rows if r['identity']['task_id']==tid and r['identity']['arm']==a and r['identity']['call_index']==0) for a in core['record_arms']]
            requests=[output/'records'/r['identity']['record_id']/'request.json' for r in initial]
            ready=all(f.exists() for f in requests);reqs=[read(f) for f in requests] if ready else []
            reproducibility.append({'task_id':tid,'both_requests':ready,'prompt_ids_equal':reqs[0]['input_token_ids']==reqs[1]['input_token_ids'] if ready else None,
               'seeds_equal':reqs[0]['seed']==reqs[1]['seed'] if ready else None,
               'response_text_equal':initial[0]['response']['text']==initial[1]['response']['text'] if all(r['response'] for r in initial) else None})
    interval=None
    if core['run_id']=='N14':
        import random
        differences=[int(t['arms']['selected_agent']['top2_exact'])-int(t['arms']['direct_grid']['top2_exact']) for t in tasks]
        rng=random.Random(1015);samples=sorted(sum(rng.choice(differences) for _ in differences)/len(differences) for _ in range(10000))
        interval={'method':'paired task-cluster percentile bootstrap,10000 replicates','seed':1015,'point_delta':sum(differences)/len(differences),
                  'lower95':samples[249],'upper95':samples[9749],'exposed_tuning_only':True}
    return {'format':'irisx/nextphase-report-v1','run_id':core['run_id'],'core_sha256':manifest['core_sha256'],'groups':groups,'task_outcomes':tasks,
            'physical_model_usage':physical,'shared_pool_cost_semantics':'N12 full shared proposal cost charged to each standalone arm; physical spend once' if core['run_id']=='N12' else None,
            'first_root_reproducibility':reproducibility,'paired_top2_interval':interval,'search_ledger_complete':search_complete,
            'confirmation_used':False,'training_performed':False,'gold_exported':False,'official_score':None,
            'interpretation':'Exposed engineering tasks. Language, demo fit, selected exact and oracle are distinct. Matched caps do not equal actual compute.'}


def finalize(output):
    output=Path(output);inventory=_evidence_inventory(output)
    write(output/'final-inventory.json',{'format':'irisx/nextphase-final-inventory-v1','files':inventory,
           'meaning':'Closed post-score artifact inventory; integrity, not a digital signature'})
    import zipfile
    destination=output.with_name(output.name+'-evidence.zip')
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(output).as_posix())
    return {'path':str(destination),'sha256':file_sha(destination),'bytes':destination.stat().st_size}


def verify_final_inventory(output):
    output=Path(output);inventory=read(output/'final-inventory.json')
    if inventory.get('format')!='irisx/nextphase-final-inventory-v1':raise ValueError('Final inventory format')
    actual=_evidence_inventory(output)
    if set(actual)!=set(inventory['files'])|{'final-inventory.json'}:raise ValueError('Final artifact closed inventory changed')
    for name,sha in inventory['files'].items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or actual[name]!=sha:raise ValueError('Final artifact hash changed')
    return inventory


_PRIOR_TEMPORARIES=[]
_PRIOR_CACHE={}
def materialize_prior(path):
    path=Path(path).resolve()
    if path.is_dir():return path
    if not path.is_file():raise ValueError('Prior evidence path missing')
    identity=file_sha(path)
    if identity in _PRIOR_CACHE:return _PRIOR_CACHE[identity]
    import zipfile,tempfile,stat
    temporary=tempfile.TemporaryDirectory(prefix='iris-suite-prior-');destination=Path(temporary.name)
    try:
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist();names=[i.filename for i in infos]
            if len(names)!=len(set(names)) or len(names)>20000 or sum(i.file_size for i in infos)>250*1024*1024:
                raise ValueError('Prior archive inventory/size limit')
            for info in infos:
                p=Path(info.filename)
                if info.is_dir() or p.is_absolute() or '..' in p.parts or '\\' in info.filename or stat.S_ISLNK(info.external_attr>>16):
                    raise ValueError('Prior archive unsafe member')
                target=destination/p;target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(info) as source,target.open('xb') as stream:
                    import shutil
                    shutil.copyfileobj(source,stream,length=1024*1024)
        verify_final_inventory(destination)
    except BaseException:
        temporary.cleanup();raise
    _PRIOR_TEMPORARIES.append(temporary);_PRIOR_CACHE[identity]=destination
    return destination


def require_security_release():
    release=read(ROOT/'SECURITY-RELEASE.json')
    if release.get('status')!='approved':raise ValueError('Independent security release required')
    for name in ('arc_bounded_v2.py','arc_program_v2.py'):
        if release['files'].get(name)!=file_sha(ROOT/name):raise ValueError('Security-reviewed interpreter hash differs')
    return release


def _safe_output(base,roots=()):
    base=Path(base)
    if not base.is_absolute() or any(p.is_symlink() for p in (base,*base.parents)):
        raise ValueError('Absolute non-symlink output required')
    if any(base.resolve().is_relative_to(Path(root).resolve()) for root in roots):raise ValueError('Output overlaps immutable input')
    return base


def launch(cfg,run_id,*,enabled=False,prior_paths=None):
    if type(enabled) is not bool:raise ValueError('Explicit Boolean manual switch required')
    if not enabled:return {'status':'disabled','run_id':run_id,'generate_calls':0,'training_calls':0,'files_written':0}
    spec=spec_for(run_id);verify_sources();require_security_release();prior_paths=prior_paths or {}
    base=_safe_output(cfg['output_root'],[v for k,v in cfg.items() if k.endswith('_root') and k!='output_root' and v])
    try:gate=resolve_gate(run_id,prior_paths)
    except Exception as exc:
        gate={'status':'blocked','reason':'invalid-prerequisite','error':{'type':type(exc).__name__,'message':str(exc)[:2000]}}
    output=base/('iris-x-'+run_id.lower()+'-20261009')
    output.mkdir(parents=True,exist_ok=False)
    if gate['status']=='blocked':
        receipt={**gate,'run_id':run_id,'source_lock_sha256':file_sha(ROOT/'source-lock.json'),'generate_calls':0,'training_calls':0}
        write(output/'blocked.json',receipt);archive=finalize(output)
        progress('EXPERIMENT-BLOCKED',**receipt,archive=archive);return {**receipt,'archive':archive,'output':str(output)}
    write(output/'gate.json',gate)
    if run_id=='N13':
        relevant=('arc_suite.py','arc_suite_policy.py','arc_bounded_v2.py','arc_program_v2.py','arc_typed_ir.py','arc_curriculum.py','DESIGN-FROZEN.json','SECURITY-RELEASE.json','source-lock.json')
        source_dir=output/'source';source_dir.mkdir()
        for name in relevant:
            with (source_dir/name).open('xb') as stream:stream.write((ROOT/name).read_bytes())
        write(output/'run-identity.json',{'format':'irisx/nextphase-cpu-run-identity-v1','run_id':run_id,
            'source_lock_sha256':file_sha(ROOT/'source-lock.json'),'design_sha256':file_sha(ROOT/'DESIGN-FROZEN.json'),
            'seed':1015,'host_python_version':sys.version,'source_copy_scope':'CPU curriculum-relevant sources; complete lock binds the published notebook payload',
            'arc_tasks_used_for_generation':False,'gpu_used':False,'training_performed':False})
        v=component('arc_program_v2');curriculum=component('arc_curriculum');started=time.monotonic();last=started;calls=0;attempts=0
        def verify(source,value,timeout_seconds=3):
            nonlocal last,calls,attempts
            attempts+=1
            receipt=v.verify_program(source,value,str(ROOT/'arc_bounded_v2.py'),timeout_seconds=timeout_seconds);calls+=1
            if time.monotonic()-last>=20:
                progress('curriculum-running',verification_calls=calls,elapsed_seconds=round(time.monotonic()-started));last=time.monotonic()
            return receipt
        verify.provenance={'fresh_os_limited_child_per_call':True,'interpreter_sha256':file_sha(ROOT/'arc_bounded_v2.py'),'verifier_sha256':file_sha(ROOT/'arc_program_v2.py')}
        try:
            result=curriculum.make_curriculum(output/'curriculum',verify,seed=1015,episodes=512,max_verifications=1024,wall_seconds=1200)
            summary={'status':'complete','run_id':run_id,'result':result,'known_verifier_responses':calls,'attempted_verifier_calls':attempts,'raised_verifier_calls':attempts-calls,'host_python_version':sys.version,'model_calls':0,'training_performed':False,'confirmation_used':False,'wall_seconds':time.monotonic()-started}
        except BaseException as exc:
            summary={'status':'partial-or-failed','run_id':run_id,'error':{'type':type(exc).__name__,'message':str(exc)[:2000]},'known_verifier_responses':calls,'attempted_verifier_calls':attempts,'raised_verifier_calls':attempts-calls,'host_python_version':sys.version,'model_calls':0,'training_performed':False,'confirmation_used':False}
        write(output/'summary.json',summary);archive=finalize(output);progress('EXPERIMENT-FINISHED',**summary,archive=archive)
        return {**summary,'archive':archive,'output':str(output)}
    # The project evaluator stays in the immutable runtime Dataset. Solver input
    # is challenge-only; no query truth is copied into this output or subprocess.
    root=Path(cfg['runtime_root']).resolve()
    _runtime_tools(root,verify_all=True)
    from tools.arc_n1 import verify_manifest as verify_n1,verify_challenges
    original=read(root/'n1/manifest.json');verify_n1(original)
    if original!=read(ROOT/'solver-manifest-reference.json'):raise ValueError('Source N1 manifest identity differs')
    all_challenges=read(root/'n1/development-challenges.json');verify_challenges(original,all_challenges)
    tasks=list(original['core']['tuning_ids'][8:40]) if run_id=='N14' else list(ENGINEERING_TASKS)
    challenges={t:all_challenges[t] for t in tasks}
    manifest=make_manifest(run_id,original,challenges,selected_policy=gate.get('selected_policy'),gate_receipts=gate.get('receipts'))
    verify_manifest(manifest,challenges);write(output/'manifest.json',manifest);write(output/'challenges.json',challenges)
    write(output/'request.json',cfg)
    source_dir=output/'source';source_dir.mkdir()
    for name in sorted(verify_sources()['files']):
        with (source_dir/name).open('xb') as stream:stream.write((ROOT/name).read_bytes())
    with (source_dir/'source-lock.json').open('xb') as stream:stream.write((ROOT/'source-lock.json').read_bytes())
    watchdog=600 if run_id=='N5' else 32400 if run_id=='N14' else 9600
    deadline=time.monotonic()+watchdog;failure=None
    dispatch={'process':'cpu-replay' if run_id=='N5' else 'controller','returncode':0,'timed_out':False,'confirmed_stopped':True,'cancellation':None}
    progress('experiment-start',run=run_id,expected_records=len(manifest['records']),max_generate_calls=spec['max_model_calls'])
    try:
        if run_id=='N5':run_replay(manifest,challenges,output,deadline)
        else:
            cfg=_validate_config(cfg)
            if cfg['pins']!=EXPECTED_PINS:raise ValueError('Exact five existing Dataset pins required')
            from tools.arc_next_offline_interpreter import prepare_interpreter,validate_interpreter
            from tools.arc_next_offline_environment import _LAUNCHER
            destination=Path(cfg['interpreter_dir']);prep=validate_interpreter if destination.exists() else prepare_interpreter
            receipt=prep(cfg['interpreter_root'],cfg['pins']['interpreter']['manifest_sha256'],destination);write(output/'interpreter.json',receipt)
            if time.monotonic()>=deadline:raise TimeoutError('Interpreter preparation exhausted shared deadline')
            request=output/'controller-request.json';write(request,{'config':cfg,'output':str(output),'deadline':deadline,'run_id':run_id,'watchdog_seconds':watchdog})
            command=[receipt['python_executable'],'-I','-B','-S','-c',_LAUNCHER,str(ROOT/'arc_suite.py'),'controller',str(request)]
            dispatch={'process':'controller','confirmed_stopped':False};dispatch=_supervise(command,'controller',output,deadline)
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc)[:2000]};write(output/'failure.json',failure)
        if dispatch.get('confirmed_stopped') is not True:
            progress('PROCESS-STOP-UNCONFIRMED',run=run_id,error=failure)
            raise RuntimeError('No seal/evaluation/export until owned process stop confirmed') from exc
    write(output/'dispatch.json',dispatch);sealed=seal(output,manifest,dispatch)
    try:report=score(output,manifest,root/'n1/evaluator/development-solutions.json');write(output/'report.json',report)
    except Exception as exc:
        failure={'type':type(exc).__name__,'message':str(exc)[:2000]};write(output/'scoring-failure.json',failure);report=None
    blocks=read(output/'blocks.json') if (output/'blocks.json').is_file() else []
    process_ok=dispatch.get('returncode')==0 and not dispatch.get('timed_out') and not dispatch.get('cancellation')
    if run_id!='N5':process_ok=process_ok and len(blocks)==1 and all(x.get('returncode')==0 and x.get('confirmed_stopped') and not x.get('timed_out') and not x.get('cancellation') for x in blocks)
    ledger_complete=not sealed['states']['missing'] and not sealed['states']['unknown'] and not sealed['states']['verification_incomplete']
    summary={'status':'complete' if ledger_complete and report is not None and report['search_ledger_complete'] and process_ok and not failure else 'partial-or-failed',
             'run_id':run_id,'core_sha256':manifest['core_sha256'],'expected_records':len(manifest['records']),
             'record_states':{k:len(v) for k,v in sealed['states'].items()},'processes_ok':bool(process_ok),'error':failure,
             'groups':report['groups'] if report else None,'host_python_version':sys.version if run_id=='N5' else None,'training_performed':False,'confirmation_used':False,
             'watchdog':{'controller_seconds':watchdog,'per_generation_cooperative_seconds':120,
                'whole_workflow_hard_cap':False,'outside_controller':['initial verification','interpreter preparation','seal','score','export'],
                'cleanup_may_overrun':True,'paid_vm_shutdown_performed':False}}
    write(output/'summary.json',summary);archive=finalize(output);progress('EXPERIMENT-FINISHED',**summary,archive=archive)
    return {**summary,'archive':archive,'output':str(output)}


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('controller','worker'):raise SystemExit('Internal controller/worker requires one request path')
    (controller if sys.argv[1]=='controller' else worker)(read(sys.argv[2]))
