"""Offline true-ARC transfer terminal validation, independent of neural runtime.

No network, subprocess, torch, model load, target-escrow parsing or public-gold
access. ZIP bytes are streamed/CRC-checked as integrity evidence only. Accepted
content is not provider-envelope admission and never establishes effectiveness
from operational completion alone.
"""
from __future__ import annotations
import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

STATUSES = ('TRANSFER_COMPLETE','TRANSFER_PARTIAL','TRANSFER_NOT_ADMITTED','TRANSFER_FAILED')
PROFILE_ID='qwen3-14b-native-bf16-r8-c4096-transfer-v1'
ADDENDUM_SHA256='ec8354dda582077a67a4df48fbd46dbca0edd1b85fd3461626e040eda5596804'
REVISION='40c069824f4251a91eefaf281ebe4c544efd3e18'
BASE_CONTRACT_SHA256='8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0'
CAPS={'generation_calls':1600,'scoring_forwards':12000,'input_tokens':50000000,'output_tokens':3200000,'training_steps':8192,'cpu_checks':12000,'gas':2400000000}
LARGE={'full-diagnostics.json','experiment/full-report.json','training-receipts-at-exit.json'}
ASSET_PREFIX='experiment/checkpoint-assets/'
DENOMINATORS={'dev':16,'holdout':32,'ttt_dev':8,'ttt_holdout':8}
PACKAGE='tools/arc_qwen_transfer_20261012/'
SCORER_PINS = {
    'tools/arc_offline_evaluation.py': '3df3fd40c0a4db82dc6ad5c568102e45ad10efad8529412eae0623bd9f4ba016',
    'tools/arc_kaggle_submission.py': 'cdd570c99614d5eb326f9f07d86b36f80e4f5e53ec197370b5a0e03f262366bf',
    'src/irisx/arc_agi2.py': '0af942df40b76f208546a88864e84ddf521168bdb8f1fa4ce24232c36f3034a1',
    'tools/nvarc_native_multitask.py': '274cc5391ee45ee098cba4f002e31425d5bed88993c2b9319b0320c17a08fbdb',
    'tools/nvarc_native_solve_runtime.py': '56380d7c5fbb9219acfc846af275d6a334ed9460b6b6448e6feacf78be77b1c1',
    'src/irisx/__init__.py': '3ca8d59be8dae69d75bd92b279cdab54a5c411162d78544578f924264905702e',
    'src/irisx/artifacts.py': '28a7a48cbabd0f8556a1f976aebeaec3cc0824a380ab8bb4c12ba5cdfc762c95',
    'src/irisx/canonical.py': 'd2bacf5548440c865a64cb7cdfbbefcb995ec47e4e53ddfa4457964a83740a6a',
    'src/irisx/contracts.py': 'afb58a3fefe0c5482616d4cd219779c5bc9dacb30be44ea153ab85496b9af6b1',
    'src/irisx/errors.py': '45c10f3c10c958cb3cca97a26a3a0f79925ed5818ce591327d9ef1a851a6ffa4',
    'src/irisx/engine.py': 'bd08a6d9740d7696c6663410a450323c0c00cc5320bce184339ea4a98717d283',
    'src/irisx/bindings.py': 'cc0bb9698ab8803c3c951cd88d7c233661dd2a38c6f1066f7d86ac8be98f7601',
    'tools/__init__.py': 'f5ed985f7ed9e31ea3be113e86b11a7b44313f467c2e468a034ff789c7b85c76',
    'src/irisx/admission.py': '0520aa0b966ea7b2bd7f88330f6c3e0e407e428cf144458a1fda89317c38bb63',
}

def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def native_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

class ValidationError(ValueError):
    """Evidence is malformed, incomplete for its claims, or inconsistent."""

def need(value, message):
    if not value:
        raise ValidationError(message)

def integer(value, minimum=0, maximum=None):
    return type(value) is int and value >= minimum and (maximum is None or value <= maximum)

def number(value, minimum=0):
    return type(value) in (int,float) and math.isfinite(value) and value >= minimum

def hash_ok(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None

def raw_sha(raw):
    return hashlib.sha256(raw).hexdigest()

def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()

def safe_name(name):
    need(type(name) is str and 0<len(name)<4096 and '\\' not in name and ':' not in name and not any(ord(c)<32 for c in name) and not PurePosixPath(name).is_absolute()
         and all(x not in ('','.','..') for x in name.split('/')),'unsafe archive member/path')
    return name

def local_file(path, cap):
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'symlink evidence path')
    need(path.is_file() and stat.S_ISREG(path.stat().st_mode) and path.stat().st_size<=cap,'missing/nonregular/oversized file: '+str(path))
    return path

def strict_json(raw, name='JSON'):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate JSON key: '+name);result[key]=value
        return result
    try:
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValidationError('nonfinite JSON: '+name)))
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:
        raise ValidationError('invalid JSON: '+name) from exc

def json_file(path, cap=64*1024**2):
    return strict_json(local_file(path,cap).read_bytes(),str(path))

class ClosedArchive:
    """Bounded ZIP read only: no extraction and no GPU-absolute path access."""
    def __init__(self,path,*,asset=False,verify_bytes=True):
        cap=2*1024**3+2*1024**2 if asset else 544*1024**2
        expanded_cap=cap if asset else 512*1024**2
        self.path=local_file(path,cap); self.sha256=file_sha(self.path)
        self.z=zipfile.ZipFile(self.path); infos=self.z.infolist(); self.members={}
        need(0<len(infos)<=(1025 if asset else 12000),'archive member count bound')
        total=0
        for item in infos:
            name=safe_name(item.filename)
            need(name not in self.members and not item.is_dir(),'duplicate/directory ZIP member')
            mode=item.external_attr>>16
            need(stat.S_IFMT(mode) in (0,stat.S_IFREG) and not item.flag_bits&1,'unsafe ZIP entry')
            limit=32*1024**2 if asset else (64*1024**2 if name in LARGE else 16*1024**2)
            need(item.file_size<=limit,'archive member byte ceiling: '+name)
            total+=item.file_size; need(total<=expanded_cap,'uncompressed archive aggregate bound')
            self.members[name]=item
        manifest_name='checkpoint-assets-manifest.json' if asset else 'archive-manifest.json'
        self.inventory=self.json(manifest_name); files=self.inventory['files']
        need(type(files) is dict and set(self.members)==set(files)|{manifest_name},'closed ZIP inventory differs')
        for name,row in files.items():
            safe_name(name);need(type(row) is dict and set(row)=={'bytes','sha256'} and integer(row['bytes']) and hash_ok(row['sha256']),'invalid inventory entry')
            need(self.members[name].file_size==row['bytes'],'ZIP inventory length mismatch: '+name)
            if verify_bytes or not name.endswith('.safetensors'):
                need(raw_sha(self.read(name))==row['sha256'],'ZIP member SHA256 mismatch: '+name)
        if asset:
            need(self.inventory['bytes']==sum(r['bytes'] for r in files.values()) and self.inventory['bytes']<=2*1024**3 and self.inventory['physical_ledger_included'] is False,'checkpoint aggregate inventory differs')
        else:
            need(self.inventory.get('owned_process_closed') is True and self.inventory.get('public_score') is None,'unclosed evidence archive')
            need('terminal-receipt.json' not in self.members and 'checkpoints.zip' not in self.members and not any(n.startswith(ASSET_PREFIX) for n in self.members),'terminal/checkpoint assets must remain outside evidence ZIP')
        self.bytes_verified=verify_bytes

    def read(self,name):
        need(name in self.members,'missing evidence member: '+name)
        try:return self.z.read(name) # zipfile verifies CRC for every full read.
        except (zipfile.BadZipFile,RuntimeError,EOFError) as exc:raise ValidationError('ZIP CRC/read failed: '+name) from exc

    def json(self,name):return strict_json(self.read(name),name)
    def close(self):self.z.close()

def closure(proof,*,clean=False):
    required={'format','root_identity','scope','ownership_complete','closed','owned_identities','remaining','returncode','worker_returncode','forced','reaped_identities','errors'}
    need(type(proof) is dict and set(proof)==required and proof['format']=='irisx/owned-process-closure-v1'
         and proof['scope']=='dedicated-subreaper-tree' and proof['closed'] is True and proof['ownership_complete'] is True
         and proof['remaining']==[] and proof['errors']==[],'complete owned-process closure proof required')
    ids=proof['owned_identities'];need(type(ids) is list and ids and proof['root_identity'] in ids,'bound owner incarnation required')
    seen=set()
    for row in ids:
        need(type(row) is dict and set(row)=={'pid','birth','session','state'} and integer(row['pid'],1) and integer(row['birth'])
             and type(row['session']) is int and type(row['state']) is str,'invalid process incarnation')
        key=(row['pid'],row['birth']);need(key not in seen,'duplicate owned incarnation');seen.add(key)
    need(type(proof['forced']) is bool and type(proof['returncode']) is int and type(proof['worker_returncode']) is int,'closure exit status types')
    need(all(row in ids for row in proof['reaped_identities']),'unowned reaped process')
    if clean:need(proof['returncode']==proof['worker_returncode']==0 and proof['forced'] is False,'clean process completion required')

def owned_tree(archive,prefix,proof,*,clean=False):
    closure(proof,clean=clean)
    need(archive.json(prefix+'closure.json')==proof,'durable closure copy differs')
    launch=archive.json(prefix+'worker-launch.json'); supervisor=archive.json(prefix+'supervisor-result.json')
    need(launch['supervisor_identity']==proof['root_identity']==supervisor['supervisor_identity'],'supervisor incarnation binding differs')
    need(launch['worker_identity'] in proof['owned_identities'] and launch['worker_identity']==supervisor['root_identity'],'worker incarnation binding differs')
    need(supervisor['closed'] is True and supervisor['ownership_complete'] is True and supervisor['remaining']==[] and supervisor['errors']==[],'inner supervisor unclosed')
    need(supervisor['worker_returncode']==proof['worker_returncode'],'worker exit status binding differs')

def ledger_replay(raw, *, require_closed):
    rows=[strict_json(line,'physical-work.jsonl') for line in raw.splitlines()]
    need(rows and rows[0]['event']=='opened' and set(rows[0]['caps'])==set(CAPS),'physical ledger opening required')
    caps=rows[0]['caps'];need(all(integer(v,0,CAPS[k]) for k,v in caps.items()),'ledger caps enlarged')
    used=dict.fromkeys(caps,0);pending={};seen=set();events={};prefixes={};previous='0'*64
    for i,row in enumerate(rows):
        need(row.get('index')==i and row.get('previous')==previous and row.get('sha256')==raw_sha((json.dumps({k:v for k,v in row.items() if k!='sha256'},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()),'physical ledger hash chain differs')
        previous=row['sha256'];kind=row['event']
        if i==0:prefixes[previous]={'used':dict(used),'pending':False};continue
        event=row['event_id'];amounts=row.get('amounts')
        if kind=='reserved':
            need(not pending and event not in seen and type(event) is str and event,'duplicate/unresolved physical reservation')
            need(type(amounts) is dict and amounts and set(amounts)<=set(caps) and all(integer(v) for v in amounts.values()),'invalid work reservation')
            for key,value in amounts.items():used[key]+=value;need(used[key]<=caps[key],'physical cap exceeded')
            pending[event]=amounts;seen.add(event)
        elif kind in ('complete','failed','excluded'):
            need(event in pending and set(amounts)==set(pending[event]),'physical completion without reservation')
            for key,value in amounts.items():
                need(integer(value,0,pending[event][key]),'physical amount exceeds reservation');used[key]-=pending[event][key]-value
            del pending[event];events[event]=row
        elif kind=='unknown':
            need(event in pending and row['charged']==pending[event],'unknown physical work undercharged');events[event]=row
        else:need(False,'unknown ledger event')
        prefixes[previous]={'used':dict(used),'pending':bool(pending)}
    if require_closed:need(not pending,'unresolved physical work')
    return {'used':used,'pending':pending,'events':events,'last_sha256':previous,'row_count':len(rows),'caps':caps,'prefixes':prefixes}


def load_helper(name):
    need(name in ('selector_replay','generation_checks','budget_checks'),'unknown validator helper')
    path=Path(__file__).with_name(name+'.py');local_file(path,1024**2)
    spec=importlib.util.spec_from_file_location('_irisx_transfer_validator_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def local_reference(original, root):
    need(type(original) is str and type(root) is str,'absolute evidence reference required')
    p,r=PurePosixPath(original),PurePosixPath(root)
    need(p.is_absolute() and r.is_absolute() and '..' not in p.parts,'invalid absolute evidence reference')
    try:return safe_name(p.relative_to(r).as_posix())
    except ValueError as exc:raise ValidationError('foreign evidence reference') from exc


class SourceSnapshot:
    """Inspect exact source bytes without importing or executing runtime modules."""
    def __init__(self,root,mapping):
        self.root=Path(root);self.mapping=deepcopy(mapping);self.zip=None
        need(type(mapping) is dict and mapping and all(hash_ok(v) for v in mapping.values()),'source mapping required')
        for n in mapping:safe_name(n)
        if self.root.is_file():
            local_file(self.root,64*1024**2);self.zip=zipfile.ZipFile(self.root)
            infos=self.zip.infolist();names=[x.filename for x in infos]
            need(len(names)==len(set(names)) and len(names)<=5000,'duplicate/oversized source ZIP')
            need(sum(x.file_size for x in infos)<=128*1024**2,'source ZIP aggregate limit')
            for info in infos:
                safe_name(info.filename)
                need(not info.is_dir() and not info.flag_bits&1 and stat.S_IFMT(info.external_attr>>16) in (0,stat.S_IFREG) and info.file_size<=32*1024**2,'unsafe source ZIP member')
        else:
            need(self.root.is_dir() and not any(p.is_symlink() for p in (self.root,*self.root.parents)),'safe source root required')
        if self.zip:
            actual={n for n in self.zip.namelist() if PurePosixPath(n).suffix in ('.py','.json','.jinja') and '__pycache__' not in PurePosixPath(n).parts}
            need(actual==set(mapping),'source ZIP executable/data identity inventory differs')
        for name,expected in mapping.items():need(raw_sha(self.read(name))==expected,'source bytes differ: '+name)
        need(PACKAGE+'protocol.py' in mapping and PACKAGE+'runner.py' in mapping,'successor source identity absent')
        self.protocol=self.assignment(PACKAGE+'protocol.py','PROTOCOL')
        required={'format':'irisx/true-arc-transfer-protocol-v1','model':'Qwen/Qwen3-14B','revision':REVISION,
            'precision':'bf16-base-fp32-lora','rank':8,'alpha':16,'context_limit':4096,'prompt_cap':3072,
            'grid_output_cap':1024,'maximum_seconds':43200,'maximum_session_seconds':43200,
            'checkpoint_updates':[64,256],'ttt_updates':[0,8,16],'train_parents':32,'dev_parents':16,
            'holdout_parents':32,'ttt_dev_parents':8,'ttt_holdout_parents':8,'maximum_answers':2}
        need(all(type(self.protocol.get(k)) is type(v) and self.protocol[k]==v for k,v in required.items()),'source protocol bounds differ')
        selector=Path(__file__).with_name('selector_replay.py')
        need(mapping.get(PACKAGE+'transfer_selector.py')==file_sha(selector),'unreviewed selector source')
        need(mapping.get('materials/qwen14b/material-contract.json',BASE_CONTRACT_SHA256)==BASE_CONTRACT_SHA256,'historical model contract altered')

    def read(self,name):
        safe_name(name);need(name in self.mapping,'source file outside exact closure')
        if self.zip:
            try:return self.zip.read(name)
            except (KeyError,zipfile.BadZipFile) as exc:raise ValidationError('invalid source ZIP read') from exc
        return local_file(self.root/name,32*1024**2).read_bytes()

    def assignment(self,name,key):
        def literal(node):
            if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Mult,ast.Add,ast.Pow,ast.Sub)):
                a,b=literal(node.left),literal(node.right)
                need(type(a) is int and type(b) is int and abs(a)<=2**40 and abs(b)<=2**40,'bounded source constant')
                if isinstance(node.op,ast.Pow):need(0<=b<=40,'bounded source exponent');return a**b
                return a*b if isinstance(node.op,ast.Mult) else a+b if isinstance(node.op,ast.Add) else a-b
            if isinstance(node,ast.Dict):return {literal(k):literal(v) for k,v in zip(node.keys,node.values)}
            if isinstance(node,(ast.List,ast.Tuple)):return [literal(x) for x in node.elts]
            return ast.literal_eval(node)
        for node in ast.parse(self.read(name)).body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==key for t in node.targets):return literal(node.value)
        raise ValidationError('missing exact source constant: '+key)

    def close(self):
        if self.zip:self.zip.close()


def source_identity(root):
    root=Path(root)
    return {p.relative_to(root).as_posix():file_sha(p) for p in sorted(root.rglob('*')) if p.is_file() and p.suffix in ('.py','.json','.jinja') and '__pycache__' not in p.parts}


def validate_clocks(request,terminal,*,synthetic):
    c=request['config'];start=c['started_epoch'];duration=c.get('maximum_seconds',43200)
    need(number(start,1) and integer(duration,120,43200),'invalid actual epoch/duration')
    need(synthetic or duration==43200,'production program duration changed')
    need(terminal['predispatch_started_epoch']==start and terminal['maximum_seconds']==duration and terminal['global_deadline_epoch']==start+43200 and terminal['effective_deadline_epoch']==start+(duration if synthetic else 42000),'deadline origin reset/changed')
    end=terminal['completed_epoch'];need(number(end) and start<=end,'invalid terminal completion epoch')
    cutoff=duration if synthetic else 42000
    if not synthetic:need(terminal.get('execution_cutoff_seconds')==42000 and terminal.get('provider_runtime_seconds')==42300,'source-bound execution/provider cutoff differs')
    within=end<=start+cutoff
    need(terminal['within_probe_deadline'] is within and terminal['within_absolute_deadline'] is within,'terminal deadline flag differs')
    if terminal['status']!='TRANSFER_FAILED':need(within,'terminal closure exceeds absolute deadline')
    need(number(terminal['elapsed_seconds']) and terminal['elapsed_seconds']<=duration,'owner elapsed ceiling')
    reserve=60 if synthetic else 600
    need(number(request['hard_deadline']) and request['work_deadline']==request['hard_deadline']-reserve and terminal['work_reserve_seconds']==reserve and terminal['owner_stop_reserve_seconds']==(30 if synthetic else 540),'closure reserve changed')
    return {'started_epoch':start,'completed_epoch':end,'deadline_epoch':start+cutoff,'program_deadline_epoch':start+duration,'within_deadline':within}


def validate_model_identity(identity,synthetic,*,source=None,hardware=None):
    required={'format':'irisx/qwen14b-native-interface-v1','model_key':'qwen3-14b','profile_id':PROFILE_ID,
        'material_addendum_sha256':ADDENDUM_SHA256,'base_precision':'bfloat16','full_vocabulary_rows':151936,
        'context_limit':4096,'prompt_cap':3072,'output_cap':1024,
        'random_test_weights':synthetic,'pretrained_weights_loaded':not synthetic,'production_admitted':False}
    need(type(identity) is dict and all(type(identity.get(k)) is type(v) and identity[k]==v for k,v in required.items()),'successor native model identity differs')
    if synthetic:
        need(identity['execution_mode']=='native-qwen3-tiny-random-cpu' and identity['reference_model_id']=='Qwen/Qwen3-14B' and identity['reference_revision']==REVISION and identity['actual_layers'] in (1,2),'tiny native fixture identity differs')
    else:
        need(identity['execution_mode']=='native-qwen3-pretrained-c4096-transfer' and identity['model_id']=='Qwen/Qwen3-14B' and identity['revision']==REVISION,'production model/revision differs')
        need(identity['verified_tensor_count']==443 and identity['verified_tensor_elements']==14768307200 and identity['all_eight_weight_sha256_verified'] is True and len(identity['verified_weight_shards'])==8,'full Qwen14B material inventory differs')
        need(identity['separate_weights_and_hf_overlay'] is True and identity['provider_snapshot_identical_to_hf'] is False,'provider/HF identity conflation')
        need(source is not None and type(hardware) is dict,'packaged model contract and actual hardware receipt required')
        contract=strict_json(source.read('materials/qwen14b/material-contract.json'))
        expected_shards={n:{'bytes':r['size_bytes'],'sha256':r['sha256']} for n,r in contract['provider_files'].items() if r['role']=='base-weight'}
        expected_overlay={n:{'bytes':r['size_bytes'],'sha256':r['sha256']} for n,r in contract['overlay_files'].items()}
        need(identity['verified_weight_shards']==expected_shards and identity['verified_overlay_files']==expected_overlay,'exact approved eight weight shards/HF overlay differ')
        need(identity['provider_weight_index_sha256']==contract['provider_files']['model.safetensors.index.json']['sha256'] and identity['overlay_template_sha256']==contract['template_sha256'] and identity['overlay_vocabulary_sha256']==contract['vocabulary_sha256'],'exact model index/tokenizer template/vocabulary differ')
        need(identity['model_manifest_sha256']==identity['material_contract_sha256']==identity['predecessor_material_contract_sha256']==BASE_CONTRACT_SHA256,'immutable composite material binding differs')
        def descriptor(key):
            row=contract[key];raw=source.read('materials/qwen14b/'+row['path']);need(len(raw)==row['bytes'] and raw_sha(raw)==row['sha256'],'material descriptor differs');return strict_json(raw)
        expected_hardware=descriptor('hardware');expected_environment=descriptor('environment')
        need(identity['hardware_profile']==expected_hardware['hardware'] and all(hardware.get(k)==value for k,value in expected_hardware['hardware'].items()),'actual approved single-GPU hardware identity differs')
        need(hardware['visible_device_count']==1 and hardware['bf16_supported'] is True and hardware['torch_cuda']==expected_hardware['torch_cuda'] and hardware['driver_version']==expected_hardware['driver_version'] and hardware['cache_atol']==hardware['cache_rtol']==0.01 and hardware['fp8_admitted'] is False and hardware['four_l4_tp_admitted'] is False,'actual hardware precision/driver/runtime differs')
        environment=identity['environment']
        need(environment['environment_lock_sha256']==contract['environment']['sha256'] and environment['actual_versions']==expected_environment['versions'] and environment['python']==expected_environment['python'] and environment['complete_transitive_lock_verified'] is True and environment['wheel_root_separate'] is True,'exact actual installed environment differs')
        origins=environment['distribution_origins'];need(set(origins)==set(expected_environment['versions']) and len(set(origins.values()))==1 and all(type(p) is str and p.startswith('/kaggle/working/') and p.endswith('/site-packages') and '..' not in p.split('/') for p in origins.values()),'isolated runtime distribution origins differ')
        estimate=hardware['estimate'];expected_estimate={'base_weights_bytes':29536614400,'kv_bytes':671088640,'recurrent_bytes':0,'convolution_bytes':0,'adapter_parameter_elements':32112640,'adapter_training_bytes':513802240,'full_logits_loss_bytes':7467958272,'activation_allowance_bytes':13421772800,'allocator_workspace_reserve_bytes':8589934592,'estimated_required_bytes':60201170944,'measured':False,'memory_fit_guaranteed':False}
        need(all(type(estimate.get(k)) is type(value) and estimate[k]==value for k,value in expected_estimate.items()),'source-bound4096 memory allowance differs')
        need(number(hardware['successor_free_bytes_before_load'],60201170944+4294967296) and hardware['successor_free_bytes_before_load']<=hardware['total_memory_bytes'] and number(hardware['load_peak_allocated_bytes'],1) and hardware['load_peak_allocated_bytes']<=hardware['total_memory_bytes'],'actual model-load memory admission receipt differs')
    return {'synthetic':synthetic,'profile_id':PROFILE_ID,'model_material_verified_by_runtime':not synthetic,'base_weight_bytes_downloaded':False}


def validate_panel(archive,*,synthetic):
    dataset=archive.json('dataset/solver-dataset.json');plan=archive.json('dataset/frozen-plan.json')
    expected=json_file(Path(__file__).with_name('frozen-panel-plan.json'))
    need(dataset['format']=='irisx/true-arc-transfer-dataset-v1' and dataset['plan']==plan,'dataset/plan binding differs')
    need(dataset['denominators']==DENOMINATORS and dataset['cpu_fixture_only'] is synthetic,'fixed denominators/origin differ')
    need(dataset['public_answers_read'] is False and dataset['original_test_fields_retained'] is False,'dataset target-role violation')
    need(plan['metadata_only_before_task_reads'] is True and plan['plan_sha256']==digest({k:v for k,v in plan.items() if k!='plan_sha256'}),'panel freeze commitment differs')
    for key,n in (('train_ids',32),('dev_ids',16),('holdout_ids',32),('ttt_dev_ids',8),('ttt_holdout_ids',8)):
        need(type(plan[key]) is list and len(plan[key])==len(set(plan[key]))==n and plan[key]==expected[key],'fixed source panel changed: '+key)
    need(not set(plan['train_ids'])&set(plan['dev_ids']+plan['holdout_ids']) and not set(plan['dev_ids'])&set(plan['holdout_ids']),'panel overlap')
    if not synthetic:need(plan==expected,'production panel metadata identity differs')
    expected_cases=[scope+':'+pid for scope in ('dev','holdout') for pid in plan[scope+'_ids']]
    need([c['case_id'] for c in dataset['cases']]==expected_cases,'fixed48 case identity/order differs')
    for case in dataset['cases']:
        need(set(case)=={'case_id','parent_id','scope','demos','query_input','source'},'solver case unknown/target field')
        need(case['case_id']==case['scope']+':'+case['parent_id'] and case['parent_id'] in plan[case['scope']+'_ids'],'case parent differs')
        need(case['source']['query_source_demo_index']==len(case['demos']) and case['source']['visible_demo_indices']==list(range(len(case['demos']))),'demonstration-only query lineage differs')
    records=dataset['records'];need(type(records) is list and records,'SFT records absent')
    need({r['task_id'] for r in records}==set(plan['train_ids']),'SFT parent coverage differs')
    need(all(r['family_id']==r['task_id'] and r.get('kind')=='grid' for r in records),'equal-parent grid-only training differs')
    return dataset


def bounds_recursive(value):
    if type(value) is list:
        for x in value:bounds_recursive(x)
    elif type(value) is dict:
        for key in ('four_l4_executed','fp8_executed'):
            if key in value:need(value[key] is False,'unsupported execution claim')
        if {'started_monotonic','completed_monotonic','deadline_monotonic'}<=set(value):
            start,end,deadline=(value[k] for k in ('started_monotonic','completed_monotonic','deadline_monotonic'))
            need(all(number(x) for x in (start,end,deadline)) and end>=start,'invalid native call clock')
            if 'late' in value:need(value['late'] is (end>=deadline),'native call deadline flag differs')
            if value.get('status')=='complete' or value.get('valid') is True:need(end<deadline,'native call completed beyond deadline')
            if 'work_deadline_monotonic' in value:
                cap=180 if value.get('call_kind')=='generation' else 120
                if value.get('call_kind')=='generation':load_helper('budget_checks').validate_window(value)
                else:need(deadline<=value['work_deadline_monotonic'] and deadline<=start+cap,'native per-call ceiling')
        for x in value.values():bounds_recursive(x)
    elif type(value) is float:need(math.isfinite(value),'nonfinite receipt')


def native_coverage(archive,ledger,*,complete):
    seen={};cache_events=set()
    def visit(value):
        if type(value) is list:
            for x in value:visit(x)
        elif type(value) is dict:
            eid=value.get('physical_event_id')
            if eid is not None and ('forward_input_tokens' in value or 'nll_sum' in value):
                need(eid in ledger['events'],'native receipt missing physical event')
                if eid in seen:need(seen[eid]==value,'native receipt duplicate changed')
                seen[eid]=value;event=ledger['events'][eid];amount=event.get('amounts',{});dispatch=value.get('dispatched')
                need(type(dispatch) is bool,'native dispatch flag must be Boolean')
                if 'generation_calls' in amount:
                    need(amount=={'generation_calls':int(dispatch),'input_tokens':value['forward_input_tokens'],'output_tokens':value['output_tokens'] if dispatch else 0},'native generation physical cost differs')
                    need(integer(value['output_tokens'],0,1024) and value['output_tokens']==len(value['output_token_ids']) and all(integer(t,0,151935) for t in value['output_token_ids']),'native generation token receipt differs')
                elif 'scoring_forwards' in amount:
                    need(amount=={'scoring_forwards':int(dispatch),'input_tokens':value['input_tokens'] if dispatch else 0},'native scoring physical cost differs')
                    if value.get('valid'):need(number(value['nll_sum']) and integer(value['token_count'],1,1024),'native NLL receipt differs')
                if value.get('valid'):need(event['event']=='complete','valid receipt backed by failed work')
            if 'event_id' in value and 'input_ids' in value and 'use_cache' in value:
                eid=value['event_id'];cache_events.add(eid)
                need(eid in ledger['events'] and ledger['events'][eid]['amounts']=={'scoring_forwards':1,'input_tokens':len(value['input_ids'])},'cache forward physical event differs')
                need(value['input_ids_sha256']==digest(value['input_ids']) and value['input_tokens']==len(value['input_ids']),'cache token commitment differs')
            for x in value.values():visit(x)
    for name in archive.members:
        # Public gold and local target escrows are never parsed or scored here.
        if not name.endswith('.json') or name.endswith('.timing.json') or 'target-escrow' in name or '/upstream/data/evaluation/' in name:continue
        obj=archive.json(name);bounds_recursive(obj);visit(obj)
    expected={eid for eid,e in ledger['events'].items() if e.get('amounts',{}).get('generation_calls',0)>0 or e.get('amounts',{}).get('scoring_forwards',0)>0 and eid not in cache_events}
    missing=sorted(expected-set(seen))
    if complete:need(not missing,'native calls lack durable receipts: '+str(missing[:3]))
    return {'native_receipts':len(seen),'cache_forward_events':len(cache_events),'missing_returned_native_receipts':missing}


def validate_phase_artifacts(archive,terminal):
    """Require durable files at actual child/experiment transition boundaries."""
    child=terminal['child'];status=terminal['status'];clean=status!='TRANSFER_FAILED'
    stage=archive.json('active-stage.json')
    need(stage['status']=='closed','child stage marker is not closed')
    admitted_phase=status in ('TRANSFER_COMPLETE','TRANSFER_PARTIAL') or stage['stage']=='true-arc-main-then-conditional-public-then-ttt' or bool(child.get('dev_seal') or child.get('holdout_seal'))
    performed_main=any(n.startswith('experiment/') for n in archive.members)
    required=set()
    if clean or admitted_phase or performed_main:
        required.update(('model-admission.json','calibration/calibration.json','feasibility.json','dataset/frozen-plan.json','dataset/solver-dataset.json'))
    if clean:required.update(('full-diagnostics.json','training-receipts-at-exit.json'))
    if admitted_phase or performed_main:required.add('decoder-policy.json')
    if status in ('TRANSFER_COMPLETE','TRANSFER_PARTIAL'):
        required.update(('experiment/dev-prediction-seal.json','experiment/dev-predictions-sealed.json',
            'experiment/holdout-prediction-seal.json','experiment/holdout-predictions-sealed.json',
            'experiment/ttt-predictions-sealed.json','experiment/checkpoint-receipts.json','experiment/full-report.json','main-scoring.json'))
    if status=='TRANSFER_COMPLETE':
        required.update(('experiment/training-admission.json','experiment/frozen-selection.json','experiment/public-selection.json','experiment/main-complete.json'))
    branch=child.get('public_branch',{})
    public_work=branch.get('status')=='PUBLIC_PREDICTIONS_SEALED' or branch.get('actual_generation_calls',0)>0 or branch.get('generation_calls',0)>0 or any(n.startswith('experiment/public/native/') for n in archive.members) or 'experiment/public/frozen-method.json' in archive.members
    if public_work or 'forecast' in branch:required.add('experiment/public/forecast.json')
    if 'experiment/main-complete.json' in archive.members:required.update(('experiment/public-cost-refresh.json','experiment/main-timing-boundaries.json'))
    if any(n.startswith('experiment/ttt/') for n in archive.members):required.add('experiment/ttt-predictions-sealed.json')
    missing=sorted(required-set(archive.members));need(not missing,'missing source-guaranteed phase artifacts: '+str(missing))
    if 'experiment/ttt-predictions-sealed.json' in archive.members:
        ttt=archive.json('experiment/ttt-predictions-sealed.json')
        ttt_work=ttt['status'] in ('TTT_COMPLETE','TTT_PARTIAL') or any(r.get('complete') is True for r in ttt['rows']) or any(n.startswith('experiment/ttt/') for n in archive.members)
        if ttt_work or 'planned_counts' in ttt or 'planned_counts' in child.get('ttt',{}):need('forecast' in ttt,'performed/planned TTT work omitted admission forecast')
        if ttt_work:need(ttt['forecast']['admitted'] is True,'performed TTT work was not admitted')
    if public_work:need(archive.json('experiment/public/forecast.json')['admitted'] is True,'performed public work was not admitted')
    if 'forecast' in branch:need(branch['forecast']==archive.json('experiment/public/forecast.json'),'public branch admission copy differs')
    if clean:
        diagnostics=archive.json('full-diagnostics.json')
        for key in ('status','science_complete','operational_success','main_complete','selection','dev_seal','holdout_seal','public_branch','denominators'):
            if key in diagnostics:need(diagnostics[key]==child.get(key),'child/full diagnostics phase projection differs: '+key)
        if status in ('TRANSFER_COMPLETE','TRANSFER_PARTIAL'):
            report=archive.json('experiment/full-report.json')
            need(all(diagnostics.get(k)==v for k,v in report.items()),'experiment/full diagnostics projection differs')
            need(report['ttt']==archive.json('experiment/ttt-predictions-sealed.json') and report['checkpoints']==archive.json('experiment/checkpoint-receipts.json'),'experiment durable phase receipts differ')
    return {'admitted_phase':admitted_phase,'performed_main':performed_main,'public_work':public_work}


def validate_costs(archive,request,source,ledger,*,synthetic):
    calibration=archive.json('calibration/calibration.json');feasibility=archive.json('feasibility.json')
    complete=calibration.get('completed_lengths')==[128,512,2048,4096]
    shortened=synthetic and calibration.get('fixture_calibration_lengths')==[128,512] and calibration.get('completed_lengths')==[128,512]
    need(calibration.get('status')=='complete' and (complete or shortened) and calibration.get('full_state_restoration_verified') is True,'complete native calibration required')
    need(calibration.get('cpu_fixture_only') is synthetic and (synthetic or calibration.get('full_context_measured') is True),'production4096 measurement absent')
    need(feasibility['calibration_sha256']==digest(calibration) and feasibility['denominators']==DENOMINATORS and feasibility['profile_id']=='true-arc-transfer-c4096' and feasibility['cpu_fixture_only'] is synthetic,'source-bound calibration/feasibility differs')
    measured=calibration['measurements'];stats=feasibility['measurements']
    observations=calibration['observations']
    need([r['length'] for r in observations]==calibration['completed_lengths'],'calibration observation lengths differ')
    need(all(set(r['states'])=={'base','updated','restored'} for r in observations),'calibration state ladder differs')
    forwards=[f for r in observations for state_name in ('base','updated','restored') for f in r['states'][state_name]['cache']['forwards']]
    need(forwards and all(f['status']=='complete' and f['late'] is False and f['finite_full_head'] is True and number(f['elapsed_seconds']) and integer(f['input_tokens'],1) for f in forwards),'invalid measured calibration forwards')
    full=[f for f in forwards if not f['use_cache']];prefill=[f for f in forwards if f['use_cache'] and not f['past_supplied']];decode=[f for f in forwards if f['use_cache'] and f['past_supplied']]
    updates_observed=[r['update'] for r in observations]
    need(full and prefill and decode and updates_observed and all(number(r['elapsed_seconds']) for r in updates_observed),'calibration forward/update timing classes absent')
    actual_measurements={'full_seconds_per_input':max(f['elapsed_seconds']/f['input_tokens'] for f in full),
        'prefill_seconds_per_input':max(f['elapsed_seconds']/f['input_tokens'] for f in prefill),
        'decode_seconds_per_call':max(f['elapsed_seconds'] for f in decode),
        'training_seconds_per_step':max(r['elapsed_seconds'] for r in updates_observed),
        'forward_samples':[{k:f[k] for k in ('event_id','use_cache','past_supplied','input_tokens','elapsed_seconds')} for f in forwards],
        'update_samples':updates_observed}
    need(measured==actual_measurements,'calibration timings differ from actual forward/update observations')
    need(all(stats.get(k)==v for k,v in measured.items()),'forecast timings differ from calibration')
    admission=archive.json('model-admission.json')
    need(stats['backend_load_seconds']==admission['load_elapsed_seconds'],'forecast model load duration differs')
    cap=request['config'].get('test_generation_cap',4) if synthetic else 1024
    def forecast_check(value,updates,generations,scores=0,reloads=0,production_public=False):
        cap=1024 if production_public else request['config'].get('test_generation_cap',4) if synthetic else 1024
        fixture=synthetic and not production_public
        for key in ('training_seconds_per_step','prefill_seconds_per_input','decode_seconds_per_call','full_seconds_per_input','backend_load_seconds'):
            need(number(stats.get(key)),'measured finite forecast timing absent')
        fixed=stats.get('generation_fixed_seconds',0)
        need(number(fixed),'invalid fixed generation overhead')
        gen=fixed+3072*stats['prefill_seconds_per_input']+(cap-1)*stats['decode_seconds_per_call']
        score=max(4096*stats['full_seconds_per_input'],stats['training_seconds_per_step'])
        seconds=1.5*(updates*stats['training_seconds_per_step']+generations*gen+scores*score+reloads*max(2 if fixture else 150,stats['backend_load_seconds']))
        expected={'updates':updates,'generations':generations,'scores':scores,'fresh_reloads':reloads,'forecast_seconds':seconds,
            'input_tokens':updates*4096+generations*(3072+cap-1)+scores*4096,'generation_seconds':gen,'generation_fixed_seconds':fixed,'score_seconds':score,
            'safety_multiplier':1.5,'output_cap_reserved':cap,'forecast_is_guarantee':False,'target_outcomes_used':False}
        need(all(value.get(k)==v and type(value.get(k)) is type(v) for k,v in expected.items()),'forecast arithmetic/complete-panel budget differs')
        need(number(value.get('remaining_seconds')) and hash_ok(value.get('ledger_head_sha256')),'forecast decision clock/ledger absent')
        reserve=5 if fixture else 600;slack=sum(3072+i for i in range(cap))+4096
        need(value['closure_reserve_seconds']==reserve and value['reservation_slack_input_tokens']==slack,'admission reserves differ')
        physical=value['physical_usage_at_decision'];need(set(physical)==set(CAPS) and all(integer(v,0,ledger['used'][k]) for k,v in physical.items()),'admission usage exceeds terminal physical work')
        prefix=ledger['prefixes'].get(value['ledger_head_sha256']);need(prefix is not None and prefix['pending'] is False and physical==prefix['used'],'admission physical usage differs from exact closed ledger prefix')
        need(value.get('branch_deadline_monotonic')==request['work_deadline'],'forecast branch deadline differs from owner work cutoff')
        per_call=load_helper('budget_checks').validate_admission_window(value,gen,score,generations,scores)
        allowed=per_call and seconds+reserve<=value['remaining_seconds'] and expected['input_tokens']+slack<=ledger['caps']['input_tokens']-physical['input_tokens']
        need(value['per_call_admitted'] is per_call,'per-call cost admission differs')
        if value is feasibility:allowed=allowed and calibration['behavioral_cache_admitted'] is True
        need(value['admitted'] is allowed,'whole-panel cost admission differs')
    updates=request['config'].get('test_checkpoint_updates',[1,2]) if synthetic else [64,256]
    forecast_check(feasibility,updates[-1],224,reloads=3)
    if 'decoder-policy.json' in archive.members:
        policy=archive.json('decoder-policy.json')
        expected={'format':'irisx/qwen14b-decoder-policy-v1','selected_mode':'cached','selected_profile':'true-arc-transfer-c4096',
            'profile':{'profile_id':'true-arc-transfer-c4096','decoder_mode':'cached','context_limit':4096,'grid_output_cap':1024,'program_output_cap':1024},
            'calibration_sha256':digest(calibration),'protocol_sha256':digest(source.protocol),'feasibility_sha256':digest(feasibility),
            'bounded_empirical_cache_fidelity':calibration['behavioral_cache_admitted'],'strict_numerical_allclose':calibration['strict_numerical_allclose'],
            'immutable':True,'cpu_fixture_only':synthetic}
        need(policy==expected and calibration['behavioral_cache_admitted'] is True and feasibility['admitted'] is True,'decoder policy differs from actual admitted calibration')
    if 'experiment/ttt-predictions-sealed.json' in archive.members:
        ttt=archive.json('experiment/ttt-predictions-sealed.json')
        if 'forecast' in ttt:
            dataset=archive.json('dataset/solver-dataset.json');plan=dataset['plan'];ids=plan['ttt_dev_ids']+plan['ttt_holdout_ids']
            D=sum(len(c['demos']) for c in dataset['cases'] if c['parent_id'] in ids);N=16
            counts={'parents':N,'demonstrations':D,'training_updates':16*(D+N),'fold_generations':3*D,'fold_scores':3*D,'query_generations':6*N,'generation_calls':3*D+6*N,'full_demo_retrains':N,'outer_fold_retrains':D}
            need(ttt['planned_counts']==counts,'TTT full-panel denominator budget differs')
            forecast_check(ttt['forecast'],16*(D+N),3*D+6*N,scores=3*D)
    if 'experiment/main-complete.json' in archive.members:
        need('experiment/public-cost-refresh.json' in archive.members,'completed main omitted frozen PUBLIC timing refresh')
    if 'experiment/public-cost-refresh.json' in archive.members:
        refreshed_stats=load_helper('budget_checks').validate_public_refresh(archive,request,ledger,stats)
    if 'experiment/public/forecast.json' in archive.members:
        # Independently reconstruct timing-only refresh from all actual main calls.
        need('experiment/public-cost-refresh.json' in archive.members,'PUBLIC forecast omitted frozen refresh')
        stats=refreshed_stats
        public=archive.json('experiment/public/forecast.json');forecast_check(public,0,334,reloads=2,production_public=True)
    refresh_summary=None
    if 'experiment/public-cost-refresh.json' in archive.members:
        refresh=archive.json('experiment/public-cost-refresh.json')
        refresh_summary={'status':refresh['status'],'timing_receipts':len(refresh['receipt_bindings']),
            'all_main_timing_bindings_verified':len(refresh['receipt_bindings'])==224 and refresh['boundaries'] is not None,
            'independent_refresh_arithmetic_verified':refresh['status']=='MAIN_TIMING_REFRESHED',
            'original_fallback_retained':refresh['status']=='CALIBRATION_FALLBACK',
            'selected_forecast_seconds':refresh['selected_estimate']['forecast_seconds'],'target_outcomes_used':False,
            'forecast_is_guarantee':False,'coverage':refresh['coverage']}
    return {'calibration_lengths':calibration['completed_lengths'],'full4096_measured':complete,'main_admitted':feasibility['admitted'],'forecast_is_guarantee':False,'public_refresh':refresh_summary}


def validate_seals(archive,request,dataset,terminal):
    helper=load_helper("generation_checks");prediction,packing=helper.prediction,helper.packing
    child=terminal['child'];complete=terminal['status']=='TRANSFER_COMPLETE';panels={};used_events=set()
    cases={c['case_id']:c for c in dataset['cases']}
    checkpoints=archive.json('experiment/checkpoint-receipts.json')
    updates=request['config'].get('test_checkpoint_updates',[1,2]) if request['config'].get('tiny_cpu') else [64,256]
    for scope in ('dev','holdout'):
        seal=archive.json('experiment/'+scope+'-prediction-seal.json');name='experiment/'+scope+'-predictions-sealed.json';raw=archive.read(name);payload=strict_json(raw,name)
        need(child[scope+'_seal']==seal and local_reference(seal['path'],request['output_root'])==name and seal['sealed'] is True and seal['scope']==scope and seal['file_sha256']==raw_sha(raw) and seal['payload_sha256']==digest(payload),'sealed prediction/source binding differs')
        expected=[c['case_id'] for c in dataset['cases'] if c['scope']==scope]
        need(payload['format']=='irisx/transfer-sealed-predictions-v1' and payload['scope']==scope and payload['case_ids']==expected and payload['plan_sha256']==dataset['plan']['plan_sha256'] and payload['query_targets_used'] is False,'prediction panel/target policy differs')
        methods=['base']+['sft'+str(u) for u in updates] if scope=='dev' else ['base','selected_sft']
        need(set(payload['methods'])==set(methods),'prediction method denominator differs')
        for method,rows in payload['methods'].items():
            need([r['case_id'] for r in rows]==expected,'per-method fixed panel changed')
            for row in rows:
                need(type(row['complete']) is bool and type(row['answers']) is list and len(row['answers'])<=2,'prediction row malformed')
                need(len({native_digest(a) for a in row['answers']})==len(row['answers']),'duplicate answers retained')
                if complete:need(row['complete'] is True and [g['transform_d4'] for g in row['generations']]==[0,1],'complete method lacks query transforms')
                answers=[]
                for gen in row['generations']:
                    path=local_reference(gen['receipt_path'],request['output_root']);receipt=archive.json(path)
                    side=str(PurePosixPath(path).with_suffix('.timing.json'));timing=archive.json(side)
                    need(timing.get('receipt_sha256')==raw_sha(archive.read(path)),'main generation timing sidecar linkage differs')
                    need(gen['receipt_sha256']==raw_sha(archive.read(path)) and gen['dispatched']==receipt['dispatched'] and gen['physical_event_id']==receipt.get('physical_event_id'),'prediction native receipt binding differs')
                    need(gen['inverse_applied'] is True,'prediction transform inverse missing')
                    if gen['dispatched']:
                        need(receipt['model_identity_sha256']==native_digest(child['model_identity']) and receipt['tiny_cpu'] is request['config'].get('tiny_cpu',False) and receipt['full_vocabulary_rows']==151936,'native generation model identity differs')
                        need(receipt['decoder_policy_sha256']==child['model_identity']['decoder_policy_sha256']==digest(archive.json('decoder-policy.json')) and receipt['decoder_mode']=='cached' and receipt['decoder_selection_phase']=='locked','native generation decoder policy differs')
                        cid=child['selection']['candidate_id'] if scope=='holdout' else method
                        need(receipt['adapter_state_sha256']==checkpoints[cid]['adapter_sha256'] and receipt['adapter_execution_mode']==('base' if method=='base' else 'trained'),'native generation checkpoint/adapter branch differs')
                        trace=receipt['forward_trace'];need(receipt['forward_calls']==len(trace) and sum(x['input_tokens'] for x in trace)==receipt['forward_input_tokens'],'actual native forward trace totals differ')
                        for index,step in enumerate(trace):
                            n=receipt['input_tokens']+index
                            need(step['use_cache'] is True and step['input_tokens']==(receipt['input_tokens'] if index==0 else 1) and step['cache_before']==(0 if index==0 else n-1) and step['cache_after']==n and step['attention_mask_tokens']==n and step['position_end']==n-1 and step['position_start']==(0 if index==0 else n-1) and step['finite_full_head'] is True,'native cached physical shape differs')
                    try:
                        need(gen['prediction']==prediction(receipt,gen['transform_d4']),'prediction differs from generated native text/inverse')
                        packing(archive.json(str(PurePosixPath(path).with_suffix('.packing.json'))),receipt,cases[row['case_id']],gen['transform_d4'])
                    except ValueError as exc:raise ValidationError(str(exc)) from exc
                    eid=gen['physical_event_id']
                    if eid is not None:
                        need(eid not in used_events,'reused physical generation across main panel');used_events.add(eid)
                    if gen['prediction'] is not None and gen['prediction'] not in answers:answers.append(gen['prediction'])
                need(row['answers']==answers[:2],'prediction top-two projection differs')
        panels[scope]=payload
    if complete:
        selection=archive.json('experiment/frozen-selection.json');need(child['selection']==selection,'child selection projection differs')
        for filename,includes_base in (('frozen-selection.json',False),('public-selection.json',True)):
            value=archive.json('experiment/'+filename);rankings=value['rankings'];candidates=['base']+['sft'+str(u) for u in updates] if includes_base else ['sft'+str(u) for u in updates]
            need(value['format']=='irisx/transfer-frozen-sft-selection-v1' and value['selection_sha256']==digest({k:v for k,v in value.items() if k!='selection_sha256'}),'selection commitment differs')
            need(value['selection_uses_holdout_targets'] is False and value['includes_frozen_base'] is includes_base and value['dev_prediction_file_sha256']==child['dev_seal']['file_sha256'] and value['plan_sha256']==dataset['plan']['plan_sha256'],'selection target/panel boundary differs')
            need({r['candidate_id'] for r in rankings}==set(candidates) and len(rankings)==len(candidates),'selection omitted candidate')
            for r in rankings:need(r['denominator']==16 and all(integer(r[k],0,16) for k in ('exact','shape','valid')) and r['exact']<=r['shape']<=r['valid'],'selection metrics invalid')
            need(rankings==sorted(rankings,key=lambda r:(-r['exact'],-r['shape'],-r['valid'],r['update'])) and value['candidate_id']==rankings[0]['candidate_id'],'dev-only selector order differs')
    return panels


def validate_ttt(archive,request,dataset):
    select_answers=load_helper("selector_replay").select_answers
    helper=load_helper("generation_checks");prediction,packing=helper.prediction,helper.packing
    ttt=archive.json('experiment/ttt-predictions-sealed.json');plan=dataset['plan'];ids=set(plan['ttt_dev_ids']+plan['ttt_holdout_ids'])
    cases=[c for c in dataset['cases'] if c['parent_id'] in ids]
    need(ttt['denominators']=={'dev':8,'holdout':8} and [r['case_id'] for r in ttt['rows']]==[c['case_id'] for c in cases],'TTT fixed subset denominator differs')
    done=0
    for case,row in zip(cases,ttt['rows']):
        if not row['complete']:
            need(row['answers']==[],'unfinished TTT row must abstain');continue
        done+=1;base='experiment/ttt/'+case['parent_id']+'/'
        global_adapter=row['candidate_state_hashes']['ttt0'][0]
        for reset_name in [f'fold-{i}-reset.json' for i in range(len(case['demos']))]+['full-demo-reset.json']:
            reset=archive.json(base+reset_name);need(reset['restored'] is True and reset['adapter_sha256']==global_adapter and reset['caller_rng_restored'] is True and reset['optimizer_cleared'] is True,'TTT global state/reset receipt differs')
        inputs=archive.json(base+'selector-inputs.json')
        task={'task_id':case['case_id'],'demonstrations':[{'demo_id':str(i),**d} for i,d in enumerate(case['demos'])],'query_input':case['query_input']}
        need(inputs['task']==task and inputs['policy']==row['policy'],'TTT task/policy source lineage differs')
        replay=select_answers(inputs['task'],inputs['policy'],inputs['candidates'])
        need(replay==row['selection'] and row['answers']==[x['grid'] for x in replay['answers']],'demo-only TTT selector replay differs')
        need(row['global_reset_verified'] is True and row['outer_folds']==len(case['demos']) and row['full_demo_retrains']==1,'TTT fold/reset coverage differs')
        for candidate in inputs['candidates']:
            update=int(candidate['candidate_id'][3:])
            for i,fold in enumerate(candidate['folds']):
                binding=archive.json(base+f'fold-{i}-binding-{update}.json');score=archive.json(base+f'fold-{i}-score-{update}.json')
                need(fold['receipt_sha256']==digest(binding) and binding['score_sha256']==digest(score),'TTT fold scorer receipt differs')
                need(binding['heldout_demo_id']==str(i) and binding['trained_demo_ids']==fold['adaptation_demo_ids'] and binding['source']==case['source'] and binding['state_sha256']==row['candidate_state_hashes'][candidate['candidate_id']][i],'TTT held-out demo leaked or source changed')
                need(fold['nll_sum']==score['nll_sum'] and fold['token_count']==score['token_count'] and score['valid'] is True and score['dispatched'] is True,'TTT NLL projection differs')
                gen=binding['generation'];genpath=local_reference(gen['receipt_path'],request['output_root']);raw=archive.read(genpath)
                foldcase={'case_id':case['case_id']+':fold'+str(i),'demos':[d for j,d in enumerate(case['demos']) if i!=j],'query_input':case['demos'][i]['input']}
                try:
                    packing(archive.json(str(PurePosixPath(genpath).with_suffix('.packing.json'))),strict_json(raw),foldcase,0)
                    need(gen['prediction']==prediction(strict_json(raw),0),'TTT native fold prediction differs')
                except ValueError as exc:raise ValidationError(str(exc)) from exc
                need(gen['receipt_sha256']==raw_sha(raw) and fold['prediction']==gen['prediction'],'TTT fold generation differs')
                if update:
                    train=archive.json(base+f'fold-{i}-train-{update}.json');need(train['status']=='complete' and train['optimizer_steps']==8,'TTT outer-fold update incomplete')
            for op,pred in enumerate(candidate['query_predictions']):
                raw=archive.read(base+f'query-{update}-{op}.json');need(pred['receipt_sha256']==raw_sha(raw),'TTT query native receipt differs')
                try:
                    need(pred['grid']==prediction(strict_json(raw),op),'TTT native query projection differs')
                    packing(archive.json(base+f'query-{update}-{op}.packing.json'),strict_json(raw),case,op)
                except ValueError as exc:raise ValidationError(str(exc)) from exc
            if update:
                train=archive.json(base+f'full-demo-train-{update}.json');need(train['status']=='complete' and train['optimizer_steps']==8,'TTT query update incomplete')
        need(ttt['status'] in ('TTT_PARTIAL','TTT_COMPLETE'),'completed TTT row contradicts phase')
    if ttt['status']=='TTT_COMPLETE':need(done==16,'TTT complete without all16 parents')
    return {'status':ttt['status'],'complete_rows':done,'denominators':{'dev':8,'holdout':8},'selector_source_sha256':file_sha(Path(__file__).with_name('selector_replay.py'))}



CHECKPOINT_POLICY_MEMBER=PACKAGE+'checkpoint_policy.py'
CHECKPOINT_MEMBER='tools/arc_qwen_portfolio_20261012/checkpoints.py'
CHECKPOINT_SCHEDULES={'global':('transfer-global-64-256-v1','global_grid','global',[0,64,256],False),
    'fixture':('transfer-fixture-1-2-v1','global_grid','global',[0,1,2],True),
    'ttt':('transfer-ttt-0-8-16-v1','representative_ttt','task',[0,8,16],False)}

def exact(left,right):
    """Type-sensitive JSON equality; bool/float cannot impersonate an integer."""
    return canonical(left)==canonical(right)

def checkpoint_contract(source,kind):
    need(kind in CHECKPOINT_SCHEDULES,'unknown closed checkpoint schedule')
    sid,branch,scope,updates,fixture=CHECKPOINT_SCHEDULES[kind]
    return {'format':'irisx/transfer-checkpoint-schedule-v1','schedule_id':sid,
        'scope':scope,'allowed_updates':updates,'fixture_only':fixture,'branch_id':branch,
        'protocol_sha256':digest(source.protocol),
        'source_sha256':{name:source.mapping[PACKAGE+name] for name in ('checkpoint_policy.py','protocol.py')}}

def checkpoint_run_kind(request):
    config=request['config'];tiny=config.get('tiny_cpu',False)
    updates=config.get('test_checkpoint_updates',[1,2] if tiny else [64,256])
    need(type(updates) is list and all(type(u) is int for u in updates),'integer checkpoint update list required')
    if updates==[1,2]:
        need(tiny is True and config.get('test_fixture_dataset') is True,'fixture checkpoint schedule requires explicit tiny fixture data')
        return 'fixture'
    need(updates==[64,256],'closed production checkpoint update schedule required')
    return 'global'

def checkpoint_source_identity(source):
    base='tools/arc_learning_agent_20261011/'
    names={base+n for n in ('training.py','data.py','grid_codec.py','native_model.py','stability.py',
        'qwen14b_model.py','qwen14b_training.py','qwen14b_contract.py','qwen14b_profiles.py',
        'qwen14b_backend.py','qwen14b_admission.py','qwen14b_probe.py')}
    names.update(('tools/arc_next_training.py','tools/arc_next_models.py','src/irisx/arc_nvarc_data.py'))
    prefixes=('tools/arc_qwen_probe_20261012/','tools/arc_qwen_portfolio_20261012/',PACKAGE)
    names.update(n for n in source.mapping if any(n.startswith(prefix) and '/' not in n[len(prefix):]
                 and n.endswith('.py') for prefix in prefixes))
    need(names<=set(source.mapping),'checkpoint trainer source closure missing')
    return {n:source.mapping[n] for n in sorted(names)}

def checkpoint_config(source,archive,request):
    # Replay the unchanged Trainer defaults, Qwen adapter defaults and exact
    # child factory overrides. Never import runtime modules to inspect them.
    config=source.assignment('tools/arc_learning_agent_20261011/training.py','DEFAULTS')
    protocol=source.protocol
    config.update(model_key='qwen3-14b',tiny_cpu=request['config'].get('tiny_cpu',False),
        lora_rank=8,lora_alpha=16,max_sequence_tokens=4096,seed=protocol['seed'],
        learning_rate=protocol['learning_rate'],task_learning_rate=protocol['task_learning_rate'],
        gradient_checkpointing=True,stability_mode=True,accumulation_target_tokens=1024,
        accumulation_max_microbatches=1,warmup_steps=4,schedule_steps=256,
        task_schedule_steps=16,task_warmup_steps=1,task_augmentations=8,objective_cycle=['grid'],
        max_supervised_tokens=4000000,max_input_tokens=16000000,
        decoder_policy_sha256=digest(archive.json('decoder-policy.json')),
        split_manifest=archive.json('dataset/solver-dataset.json')['manifest'])
    return config

def checkpoint_records(archive):
    dataset=archive.json('dataset/solver-dataset.json');records=dataset['records']
    admission=archive.json('experiment/training-admission.json');rows=admission['rows']
    need(type(admission['full_record_denominator']) is int and type(admission['eligible_records']) is int and
         type(admission['records_count']) is int and len(rows)==len(records)==admission['full_record_denominator'] and
         admission['whole_target_truncation'] is False,'checkpoint training-admission denominator differs')
    admitted=[]
    for row,record in zip(rows,records):
        need(type(record) is dict and record.get('record_id')==native_digest({k:v for k,v in record.items() if k!='record_id'}),'checkpoint record content identity differs')
        need(row['record_id']==record['record_id'] and row['parent_id']==record['task_id'] and type(row['eligible']) is bool,'checkpoint record admission/order differs')
        if row['eligible']:admitted.append(record)
    need(admitted and len(admitted)==admission['eligible_records']==admission['records_count'] and
         {r['task_id'] for r in admitted}==set(dataset['plan']['train_ids']),'checkpoint admitted training panel differs')
    # These identity projections are emitted by the repaired writer in addition
    # to the original row-level native admission, and are independently replayed.
    need(admission['record_ids']==[r['record_id'] for r in admitted] and
         admission['records_sha256']==native_digest(admitted),'checkpoint admitted record commitment differs')
    return admitted

def validate_checkpoint_binding(binding,source,*,kind,update,records,config,provenance,model_identity=None):
    expected_schedule=checkpoint_contract(source,kind)
    need(type(update) is int and update in expected_schedule['allowed_updates'],'checkpoint update outside closed schedule')
    need(exact(binding.get('checkpoint_schedule'),expected_schedule),'checkpoint source-bound schedule differs')
    need(binding['branch_id']==expected_schedule['branch_id'] and binding['physical_ledger_included'] is False,
         'checkpoint branch/physical accounting differs')
    need(binding['precision']=='bf16-base-fp32-lora' and type(binding['rank']) is int and binding['rank']==8 and
         type(binding['alpha']) is int and binding['alpha']==16,'checkpoint recipe differs')
    need(exact(binding['source'],checkpoint_source_identity(source)),'checkpoint exact trainer source identity differs')
    need(exact(binding['config'],config),'checkpoint exact trainer config differs')
    need(exact(binding['provenance'],provenance),'checkpoint protocol/training lineage differs')
    need(binding['records_sha256']==native_digest(records) and type(binding['records_count']) is int and
         binding['records_count']==len(records) and binding['record_ids']==[r['record_id'] for r in records],
         'checkpoint ordered record identity differs')
    need(kind!='fixture' or binding['config']['tiny_cpu'] is True,'fixture checkpoint binding cannot be production')
    if model_identity is not None:
        need(exact(binding['model']['native_identity'],model_identity),'checkpoint actual native model identity differs')
    need(binding['model']['tiny_cpu'] is config['tiny_cpu'],'checkpoint model/config fixture origin differs')
    need(binding['expanded_target_inventory']==binding['model']['qwen14b_exact_peft_recipe'],
         'checkpoint model/adapter target inventory differs')
    need(type(binding['parameter_names']) is list and binding['parameter_names'] and
         len(binding['parameter_names'])==len(set(binding['parameter_names'])),'checkpoint exact named parameters required')
    return expected_schedule

def validate_checkpoint_projection(manifest,resume,inference,saved):
    """Replay compact identity/counter metadata only; tensor payload stays opaque."""
    binding=manifest['binding'];update=saved['update']
    need(type(update) is int and type(manifest['update']) is int and manifest['update']==update and
         saved['branch_id']==binding['branch_id'],'checkpoint manifest/receipt update or branch differs')
    need(manifest['binding_sha256']==native_digest(binding) and inference['binding_sha256']==manifest['binding_sha256'] and
         exact(inference['binding'],binding) and type(inference['update']) is int and inference['update']==update,
         'inference/full checkpoint schedule or update differs')
    need(manifest['state_sha256']==resume['handle']['state_sha256']==saved['state_sha256'] and
         manifest['adapter_sha256']==resume['handle']['fingerprint']['sha256']==inference['adapter_sha256']==saved['adapter_sha256'],
         'checkpoint full-state/inference fingerprint differs')
    need(resume['handle']['identity_sha256']==native_digest({k:binding[k] for k in ('model','config','source')}),
         'checkpoint full-state identity differs')
    tree=resume['tree'];task_id=checkpoint_tree_field(tree,'task_id');schedule=binding.get('checkpoint_schedule')
    need(type(schedule) is dict,'checkpoint source-bound schedule missing')
    need(schedule.get('scope')==('global' if task_id is None else 'task'),'checkpoint schedule/resume task scope differs')
    run=checkpoint_tree_node(tree,'run_state')
    if update==0:
        need(run=={'v':None},'zero-update checkpoint has trained run state')
    else:
        need(checkpoint_tree_field(run,'steps')==update and type(checkpoint_tree_field(run,'steps')) is int and
             checkpoint_tree_field(run,'failed_update') is False,'checkpoint resume update counter differs')
        identity=checkpoint_tree_node(run,'identity')
        need(checkpoint_tree_field(identity,'config_sha256')==native_digest(binding['config']) and
             checkpoint_tree_field(identity,'data_sha256')==binding['records_sha256'] and
             checkpoint_tree_field(identity,'task_id')==task_id,'checkpoint resume training identity differs')
        scheduler=checkpoint_tree_node(tree,'scheduler')
        need(checkpoint_tree_field(scheduler,'last_epoch')==update and type(checkpoint_tree_field(scheduler,'last_epoch')) is int and
             checkpoint_tree_field(scheduler,'_step_count')==update+1 and type(checkpoint_tree_field(scheduler,'_step_count')) is int,'checkpoint scheduler update counter differs')


def compact_checkpoint(archive,files,saved,meta,request):
    original=local_reference(saved['path'],request['output_root'])
    need(original.startswith(ASSET_PREFIX) and saved['inference_path']==saved['path']+'/inference',
         'checkpoint/inference asset path differs')
    def read(filename,expected_sha):
        wrapper=archive.json(meta+filename);payload=wrapper['payload']
        need(wrapper['source_path']==str(PurePosixPath(saved['path'])/filename) and
             wrapper['source_sha256']==expected_sha==files[original+'/'+filename]['sha256'] and
             raw_sha((json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode())==expected_sha,
             'checkpoint compact metadata binding differs: '+filename)
        return payload
    manifest=read('manifest.json',saved['manifest_sha256']);binding=manifest['binding']
    need(manifest['format']=='irisx/qwen-branch-safe-checkpoint-v1' and manifest['binding_sha256']==native_digest(binding) and
         type(manifest['update']) is int and manifest['update']==saved['update'] and
         manifest['state_sha256']==saved['state_sha256'] and manifest['adapter_sha256']==saved['adapter_sha256'],
         'full checkpoint update/state/binding differs')
    need(manifest['resume_capable'] is True and manifest['physical_ledger_included'] is False,
         'checkpoint restores physical accounting or omits resume state')
    expected_files={n[len(original)+1:]:r for n,r in files.items() if n.startswith(original+'/') and n!=original+'/manifest.json'}
    need(exact(manifest['files'],expected_files) and manifest['payload_file_bytes']==sum(r['bytes'] for r in expected_files.values()),
         'checkpoint full-state inventory differs')
    resume=read('resume/state.json',manifest['files']['resume/state.json']['sha256'])
    need(resume['format']==manifest['format'] and resume['physical_ledger_included'] is False and
         resume['gradients']=='all-cleared-none' and resume['handle']['complete_training_state'] is True and
         resume['handle']['physical_ledger_included'] is False and resume['handle']['state_sha256']==saved['state_sha256'] and
         resume['handle']['fingerprint']['sha256']==saved['adapter_sha256'],'full-state resume boundary differs')
    need(resume['handle']['identity_sha256']==native_digest({'model':binding['model'],'config':binding['config'],'source':binding['source']}),
         'checkpoint resume model/config/source identity differs')
    inference=read('inference/adapter_model.safetensors.index.json',saved['inference_manifest_sha256'])
    need(inference['format']==manifest['format'] and inference['resume_capable'] is False and
         inference['binding_sha256']==manifest['binding_sha256'] and exact(inference['binding'],binding) and
         type(inference['update']) is int and inference['update']==manifest['update'] and
         inference['adapter_sha256']==saved['adapter_sha256'] and inference['loader']=='load_inference_adapter',
         'standalone inference checkpoint schedule/update/binding differs')
    need(inference['tokenizer_reference']==binding['model'] and inference['expanded_target_inventory']==binding['expanded_target_inventory'] and
         inference['adapter_keys']==resume['adapter_keys'] and set(inference['adapter_keys'])==set(binding['parameter_names']),
         'inference/resume model and parameter identity differs')
    need(exact(inference['files'],{n[len('inference/'):]:r for n,r in expected_files.items()
         if n.startswith('inference/') and n!='inference/adapter_model.safetensors.index.json'}),
         'inference checkpoint inventory differs')
    validate_checkpoint_projection(manifest,resume,inference,saved)
    return manifest,resume,inference


def checkpoint_tree_node(tree,key):
    """Locate one tagged JSON metadata field without resolving any tensor."""
    need(type(tree) is dict and set(tree)=={'d'} and type(tree['d']) is list,'checkpoint tagged metadata root differs')
    rows=[row[1] for row in tree['d'] if type(row) is list and len(row)==2 and row[0]=={'v':key}]
    need(len(rows)==1,'checkpoint tagged metadata field missing/duplicated: '+key)
    return rows[0]

def checkpoint_tree_field(tree,key):
    value=checkpoint_tree_node(tree,key)
    need(type(value) is dict and set(value)=={'v'},'checkpoint scalar metadata required: '+key)
    return value['v']

def validate_representative_checkpoints(archive,request,source,inventory,config,model_identity,checkpoints,dataset):
    if 'experiment/ttt-predictions-sealed.json' not in archive.members:return 0
    ttt=archive.json('experiment/ttt-predictions-sealed.json');count=0
    cases={c['case_id']:c for c in dataset['cases']}
    for row in ttt['rows']:
        saved=row.get('representative_checkpoint')
        if row.get('complete') is True and cases[row['case_id']]['parent_id']==dataset['plan']['representative_ttt_parent']:
            need(type(saved) is dict,'completed representative task omitted checkpoint metadata receipt')
        if saved is None:continue
        count+=1;case=cases[row['case_id']];base='experiment/ttt/'+case['parent_id']+'/'
        need(count==1 and case['parent_id']==dataset['plan']['representative_ttt_parent'] and
             row['complete'] is True and saved['branch_id']=='representative_ttt' and type(saved['update']) is int and
             saved['update']==16,'representative task checkpoint case/update differs')
        for flag in ('atomic','pickle_free','resume_capable','physical_ledger_untouched'):need(saved[flag] is True,'unsafe task checkpoint receipt')
        record_doc=archive.json(base+'checkpoint-records.json');records=record_doc['records'];task=case['case_id']+':query-full-demo'
        need(record_doc['case_id']==case['case_id'] and record_doc['task_id']==task and exact(record_doc['source'],case['source']) and
             record_doc['record_ids']==[r['record_id'] for r in records] and record_doc['records_sha256']==native_digest(records),
             'representative task source/record commitment differs')
        need(type(records) is list and records and type(record_doc['records_count']) is int and
             len(records)==record_doc['records_count']==len(case['demos'])*config['task_augmentations'],
             'representative task record coverage differs')
        for record in records:
            need(record['record_id']==native_digest({k:v for k,v in record.items() if k!='record_id'}) and
                 record['task_id']==task and record['parent_ids']==[task] and record['split']=='train' and record['kind']=='grid' and
                 record['family_id']=='task-local:'+task and record['provenance']['source_task_sha256']==native_digest({'train':case['demos']}),
                 'representative task record identity/scope differs')
        manifest,resume,inference=compact_checkpoint(archive,inventory['files'],saved,
            'experiment/checkpoint-metadata/representative_ttt/',request)
        selected=archive.json('experiment/frozen-selection.json')['candidate_id']
        provenance={'source':case['source'],'global_checkpoint_sha256':checkpoints[selected]['manifest_sha256']}
        need(record_doc['global_checkpoint_sha256']==provenance['global_checkpoint_sha256'] and
             exact(row['representative_record_identity'],{k:value for k,value in record_doc.items() if k!='records'}),
             'representative task record identity projection differs')
        validate_checkpoint_binding(manifest['binding'],source,kind='ttt',update=16,records=records,config=config,
            provenance=provenance,model_identity=model_identity)
        need(checkpoint_tree_field(resume['tree'],'task_id')==task and
             checkpoint_tree_field(resume['tree'],'task_records_digest')==native_digest(records),
             'representative task resume record/scope differs')
        loaded=archive.json(base+'representative-reload.json')
        need(exact(loaded,row['representative_reload']),'representative task reload projection differs')
        need(loaded['loaded'] is True and loaded['disk_reload_verified'] is True and loaded['same_parameter_bindings'] is True and
             loaded['complete_training_state'] is True and loaded['physical_ledger_untouched'] is True and loaded['gradients_cleared'] is True and
             loaded['state_sha256']==saved['state_sha256'] and loaded['manifest_sha256']==saved['manifest_sha256'] and
             loaded['branch_id']==saved['branch_id'] and type(loaded['update']) is int and loaded['update']==16,
             'representative task full-state reload differs')
    return count


def validate_checkpoints(root,archive,request,source,*,complete,verify_checkpoint_bytes=False):
    inventory=archive.json('checkpoint-assets-manifest.json');files=inventory['files']
    if not files:
        need(not complete and inventory['bytes']==0 and inventory['complete_store'] is False,'complete transfer has no checkpoint state')
        return {'global_checkpoint_count':0,'metadata_and_reload_receipts_verified':False,'verified_archive_bytes':False,'qualification':'No checkpoint assets emitted before this terminal status.'}
    need(inventory['format']=='irisx/portfolio-checkpoint-assets-v1' and inventory['physical_ledger_included'] is False and inventory['bytes']==sum(r['bytes'] for r in files.values()),'checkpoint asset inventory differs')
    need(inventory['bytes']<=2*1024**3 and len(files)<=1024,'checkpoint asset bound')
    for name,row in files.items():need(safe_name(name).startswith(ASSET_PREFIX) and integer(row['bytes'],0,32*1024**2) and hash_ok(row['sha256']),'invalid checkpoint inventory member')
    if 'experiment/checkpoint-receipts.json' not in archive.members:
        need(not complete,'complete run omitted checkpoint receipts');return {'verified_archive_bytes':False,'qualification':'No completed checkpoint receipts.'}
    checkpoints=archive.json('experiment/checkpoint-receipts.json');kind=checkpoint_run_kind(request)
    updates=checkpoint_contract(source,kind)['allowed_updates'][1:]
    expected={'base':0,**{'sft'+str(u):u for u in updates}}
    need(type(checkpoints) is dict and set(checkpoints) in [set(list(expected)[:n]) for n in range(4)],'checkpoint set is not a reached global schedule prefix')
    if complete:need(set(checkpoints)==set(expected) and inventory['complete_store'] is True,'three full-state global checkpoints required')
    dataset=archive.json('dataset/solver-dataset.json');config=checkpoint_config(source,archive,request)
    records=checkpoint_records(archive)
    provenance={'protocol_sha256':digest(source.protocol),'plan_sha256':dataset['plan']['plan_sha256'],'task_balanced':True,'query_targets_used':False}
    model_identity=archive.json('child-summary.json')['model_identity'];global_binding=None
    for cid,saved in checkpoints.items():
        need(cid in expected and type(saved['update']) is int and saved['update']==expected[cid] and saved['branch_id']=='global_grid','checkpoint candidate/update differs')
        for flag in ('atomic','pickle_free','resume_capable','physical_ledger_untouched'):need(saved[flag] is True,'unsafe/incomplete checkpoint receipt')
        for key in ('manifest_sha256','state_sha256','adapter_sha256','inference_manifest_sha256'):need(hash_ok(saved[key]),'checkpoint state hash absent')
        manifest,resume,inference=compact_checkpoint(archive,files,saved,'experiment/checkpoint-metadata/'+cid+'/',request)
        binding=manifest['binding']
        need(checkpoint_tree_field(resume['tree'],'task_id') is None,'global checkpoint contains task-local resume state')
        validate_checkpoint_binding(binding,source,kind=kind,update=saved['update'],records=records,
            config=config,provenance=provenance,model_identity=model_identity)
        if global_binding is not None:need(exact(binding,global_binding),'global checkpoints changed source/config/records/model identity')
        global_binding=binding
        if saved['update']:
            reload=archive.json('experiment/fresh-reload-'+str(saved['update'])+'.json');loaded=reload['loaded']
            need(reload['fresh_backend_reload_verified'] is True and loaded['loaded'] is True and loaded['disk_reload_verified'] is True and loaded['same_parameter_bindings'] is True and loaded['complete_training_state'] is True and loaded['physical_ledger_untouched'] is True and loaded['gradients_cleared'] is True and loaded['state_sha256']==saved['state_sha256'] and loaded['manifest_sha256']==saved['manifest_sha256'] and loaded['branch_id']==saved['branch_id'] and type(loaded['update']) is int and loaded['update']==saved['update'],'fresh full-state checkpoint reload differs')
    task_count=validate_representative_checkpoints(archive,request,source,inventory,config,model_identity,checkpoints,dataset)
    actual=Path(root)/'checkpoints.zip';verified=False
    if verify_checkpoint_bytes:
        need(actual.is_file(),'requested checkpoint archive bytes missing')
        assets=ClosedArchive(actual,asset=True,verify_bytes=True)
        try:need(assets.inventory==inventory,'checkpoint/evidence inventory differs');verified=True
        finally:assets.close()
    return {'global_checkpoint_count':len(checkpoints),'representative_task_checkpoint_count':task_count,
        'schedule_config_records_source_identity_verified':True,'metadata_and_reload_receipts_verified':True,'verified_archive_bytes':verified,
        'qualification':'All checkpoint archive bytes, CRC and hashes verified.' if verified else 'Actual checkpoint archive bytes were not verified; compact full-state/inference metadata and reload receipts only. No model/checkpoint download performed.'}


def validate_public_rows(report,pool):
    """Re-aggregate truth-free scorer booleans; never load answer grids."""
    from collections import Counter
    records=pool['records'];need(type(records) is list and len(records)==120,'public pool task denominator differs')
    tasks={};tests={}
    for rec in records:
        key=rec['task_id'];need(type(key) is str and re.fullmatch('[0-9a-f]{8}',key) and key not in tasks,'public pool task identity differs');tasks[key]=rec
        for row in rec['tests']:
            identity=(key,row['test_index']);need(integer(row['test_index'],0,20) and identity not in tests and len(row['ranked_grids'])<=2,'public pool query/answer denominator differs');tests[identity]=row
    rows=report['rows'];need(type(rows) is list and len(rows)==167,'original scorer row denominator differs');seen=set();counts=Counter();solved=Counter()
    for row in rows:
        ident=(row['task_id'],row['test_index']);need(ident not in seen and row['task_id'] in tasks and integer(row['test_index'],0,20),'original scorer query identity differs');seen.add(ident)
        rec=tasks[row['task_id']];test=tests.get(ident);counts[row['task_id']]+=1
        need(row['task_digest']==rec['task_digest'],'scorer/pool task content differs')
        if test:need(row['input_digest']==test['input_digest'] and row['pool_size']==len(test['ranked_grids']) and row['status']==test['status'],'scorer/pool query projection differs')
        else:need(row['pool_size']==0 and row['status']=='unobserved','missing pool record altered scored denominator')
        for key in ('pass1','pass2','oracle','coverage','empty_pool','pool_miss','ranking_miss','record_observed'):need(type(row[key]) is bool,'strict scorer correctness/coverage Boolean required')
        need(row['record_observed'] is (test is not None) and row['coverage'] is bool(row['pool_size']) and row['empty_pool'] is (row['pool_size']==0),'scorer observation/coverage differs')
        need(not row['pass1'] or row['pass2'],'pass@1 exceeds pass@2')
        need(row['oracle'] is row['pass2'] and row['ranking_miss'] is False and row['pool_miss'] is (row['coverage'] and not row['oracle']),'top2-only scorer attribution differs')
        need(sum(row[k] for k in ('pass2','empty_pool','pool_miss','ranking_miss'))==1,'exclusive scorer loss accounting differs')
        if row['pass2']:solved[row['task_id']]+=1
    need(set(counts)==set(tasks) and len(seen)==167 and set(tests)<=seen,'fixed public row set differs')
    for key,n in counts.items():need({i for task,i in seen if task==key}==set(range(n)),'public multiquerry indices differ')
    metric=lambda num,den,unit='test':{'numerator':num,'denominator':den,'value':num/den,'unit':unit}
    metrics={name:metric(sum(r[field] for r in rows),167) for name,field in (('pass_at_1','pass1'),('pass_at_2','pass2'),('candidate_oracle','oracle'),('candidate_coverage','coverage'),('empty_pool','empty_pool'),('pool_miss','pool_miss'),('ranking_miss','ranking_miss'))}
    metrics.update(partial_pool=metric(sum(r['pool_size']==1 for r in rows),167),unobserved_test_record=metric(sum(not r['record_observed'] for r in rows),167),task_average_pass_at_2=metric(sum(solved[k]/n for k,n in counts.items()),120,'task'),tasks_all_tests_pass_at_2=metric(sum(solved[k]==n for k,n in counts.items()),120,'task'))
    expected={'tasks':120,'tests':167,'aggregation':'test-micro, task-macro and whole-task success reported separately','metrics':metrics,'candidate_total':sum(r['pool_size'] for r in rows)}
    need(report['development_metrics']==expected,'original scorer rows/aggregate metrics differ')
    need(report['run_id']==pool['run_id'] and report['method']==pool['method'] and report['source_digest']==pool['challenges_digest'],'original scorer/pool identity differs')
    return expected


def validate_public_native(archive,request,seal,child,*,synthetic):
    helper=load_helper('generation_checks');prefix='public-prediction-seal/';pool=archive.json(prefix+'pool.json');branch=child['public_branch']
    artifact_path=local_reference(branch['artifact_path'],request['output_root']);raw=archive.read(prefix+'evidence/'+artifact_path);artifact=strict_json(raw)
    need(branch['artifact_sha256']==raw_sha(raw) and artifact['format']=='irisx/transfer-public-predictions-v1' and artifact['test_answers_read'] is False and artifact['physical_pending']=={},'sealed public native artifact differs')
    need(artifact['method']==branch['method']==seal['execution']['method'] and artifact['solver_manifest_sha256']==seal['solver_manifest_sha256'],'public selected source/method differs')
    for name in seal['files']:
        if not name.startswith('evidence/'):continue
        relative=name[len('evidence/'):];raw=archive.read(prefix+name)
        if relative in archive.members:need(raw==archive.read(relative),'public sealed copy differs from original native evidence')
        elif relative.startswith(ASSET_PREFIX):need(archive.json('checkpoint-assets-manifest.json')['files'][relative]['sha256']==raw_sha(raw),'public checkpoint seal copy differs from asset manifest')
        else:need(False,'public sealed native evidence missing original source: '+relative)
    ledger=ledger_replay(archive.read(prefix+'evidence/physical-work.jsonl'),require_closed=True)
    need(ledger['used']==child['physical_usage'],'public/terminal physical ledger differs')
    pool_tests={(r['task_id'],t['test_index']):t for r in pool['records'] for t in r['tests']};seen=set();used=set();calls=0
    need(artifact['case_count']==len(artifact['case_receipts'])<=167,'public case count differs')
    for case in artifact['case_receipts']:
        key=(case['parent_id'],case['test_index']);need(key in pool_tests and key not in seen,'foreign/duplicate public native case');seen.add(key);answers=[]
        need([g['transform_d4'] for g in case['generations']] in ([],[0],[0,1]),'public native transform order differs')
        for gen in case['generations']:
            name=local_reference(gen['receipt_path'],request['output_root']);raw=archive.read(prefix+'evidence/'+name);receipt=strict_json(raw)
            need(raw_sha(raw)==gen['receipt_sha256'] and gen['dispatched'] is receipt['dispatched'] and gen['physical_event_id']==receipt.get('physical_event_id') and gen['inverse_applied'] is True,'public native receipt commitment differs')
            packed=archive.json(prefix+'evidence/'+str(PurePosixPath(name).with_suffix('.packing.json')))
            need(packed['task_id']=='public:'+key[0]+':'+str(key[1]) and packed['query_targets_used'] is False and packed['partial_grids_or_targets_truncated'] is False and packed['context_limit']==4096 and packed['output_cap']==1024,'public input/prompt identity differs')
            if receipt['dispatched']:
                eid=gen['physical_event_id'];need(eid in ledger['events'] and eid not in used,'public native event missing/reused');used.add(eid);calls+=1
                need(ledger['events'][eid]['amounts']=={'generation_calls':1,'input_tokens':receipt['forward_input_tokens'],'output_tokens':receipt['output_tokens']},'public native physical cost differs')
                need(receipt['tiny_cpu'] is synthetic and receipt['adapter_state_sha256']==artifact['method']['adapter_sha256'] and receipt['adapter_execution_mode']==('base' if artifact['method']['role']=='frozen_base' else 'trained'),'public native model/adapter differs')
                need(packed['prompt_sha256']==native_digest(packed['prompt']) and receipt['rendered_prompt_sha256']==raw_sha(packed['prompt'].encode()) and packed['prompt_tokens']==receipt['input_tokens'],'public rendered native prompt commitment differs')
                if not synthetic:need(receipt['model_identity_sha256']==native_digest(child['model_identity']) and receipt['decoder_policy_sha256']==digest(archive.json('decoder-policy.json')),'public actual production identity differs')
            else:need(gen['physical_event_id'] is None and receipt.get('whole_example_excluded') is True,'public undispatched receipt differs')
            try:prediction=helper.prediction(receipt,gen['transform_d4'])
            except ValueError as exc:raise ValidationError(str(exc)) from exc
            need(gen['prediction']==prediction,'public native output grid/inverse differs')
            if prediction is not None and prediction not in answers:answers.append(prediction)
        expected={'attempt_1':answers[0] if answers else None,'attempt_2':answers[1] if len(answers)>1 else None}
        need(artifact['predictions'][key[0]][key[1]]==expected and pool_tests[key]['ranked_grids']==answers,'public top-two pool/native projection differs')
    need(set(pool_tests)==seen and calls==branch['actual_generation_calls']==seal['execution']['generation_calls'] and len(seen)==seal['execution']['observed_queries'],'sealed public physical/query coverage differs')
    return pool


def validate_public(archive,request,terminal,source,*,synthetic):
    summary=terminal.get('public_evaluation')
    if not summary:return {'status':terminal.get('public_evaluation_status','PUBLIC_NOT_RUN'),'goal_met':False,'eligible_complete_production_public_measurement':False}
    if summary['status'] in ('SCORING_NOT_ADMITTED','SCORING_BLOCKED'):
        need(summary['goal_met'] is False and summary['official_score'] is None,'blocked scorer claimed goal');return summary
    need(summary==archive.json('public-evaluation/public-summary.json'),'terminal/public evaluator projection differs')
    need(summary['format']=='irisx/transfer-public-evaluation-v1' and summary['status'] in ('PUBLIC_EVALUATION_COMPLETE','PUBLIC_EVALUATION_PARTIAL'),'public scorer status differs')
    seal=archive.json('public-prediction-seal/prediction-seal.json');seal_sha=raw_sha(archive.read('public-prediction-seal/prediction-seal.json'))
    need(summary['prediction_seal_sha256']==seal_sha and seal['format']=='irisx/transfer-public-prediction-seal-v1' and seal['phase']=='predictions-sealed-generation-closed' and seal['generation_may_resume'] is False,'public score lacks closed prediction seal')
    prefix='public-prediction-seal/';actual={n[len(prefix):] for n in archive.members if n.startswith(prefix)}
    need(actual==set(seal['files'])|{'prediction-seal.json'},'public seal exact inventory differs')
    for name,item in seal['files'].items():
        raw=archive.read(prefix+safe_name(name));need(len(raw)==item['bytes'] and raw_sha(raw)==item['sha256'],'public seal member bytes differ')
    need(seal['request_sha256']==raw_sha(archive.read('request.json')) and seal['result_sha256']==raw_sha(archive.read('child-summary.json')) and seal['source_identity_sha256']==digest(source.mapping),'public score/request/source identity differs')
    need(archive.json(prefix+'owner-proof.json')==terminal['closure_proof'],'public seal owner differs')
    process=archive.json('public-evaluation/process-receipt.json')
    need(process['owned_process_stopped'] is True and process['returncode']==0 and process['timed_out'] is False and process['prediction_seal_sha256']==seal_sha,'public evaluator did not close cleanly')
    if 'public-evaluation/owned-tree/closure.json' in archive.members:
        owned_tree(archive,'public-evaluation/owned-tree/',archive.json('public-evaluation/owned-tree/closure.json'),clean=True)
    need(summary['source_identity_sha256']==digest(source.mapping) and summary['scorer_sha256']==SCORER_PINS['tools/arc_offline_evaluation.py'] and all(source.mapping.get(k)==value for k,value in SCORER_PINS.items()),'original scorer/source pin differs')
    evaluator_request=archive.json('public-evaluation/request.json')
    need(evaluator_request['seal_sha256']==seal_sha and local_reference(evaluator_request['prediction_root'],request['output_root'])=='public-prediction-seal' and local_reference(evaluator_request['output_root'],request['output_root'])=='public-evaluation' and evaluator_request['solver_root']==request['config']['public_solver_root'],'public CPU scorer request/seal/path differs')
    detail=archive.json('public-evaluation/evaluator-detail.json');need({k:v for k,v in detail.items() if k!='report'}==summary and detail['report']['development_metrics']==summary['development_metrics'],'public-summary/full original scorer report projection differs')
    pool=validate_public_native(archive,request,seal,terminal['child'],synthetic=synthetic)
    validate_public_rows(detail['report'],pool)
    metric=summary['development_metrics'];score=metric['metrics']['pass_at_2'];num=score['numerator'];den=score['denominator']
    need(summary['tasks']==metric['tasks']==120 and summary['tests']==metric['tests']==den==167 and integer(num,0,167) and score['value']==num/167,'public micro denominator/arithmetic differs')
    execution=seal['execution']
    expected_complete=execution['complete_coverage'] and terminal['child']['public_branch']['status'] in ('PUBLIC_PREDICTIONS_SEALED','complete') and terminal['child']['status']=='TRANSFER_COMPLETE'
    need(execution['complete'] is expected_complete,'public phase completion differs from actual terminal branch')
    if synthetic:need(execution['production_eligible'] is False,'synthetic seal cannot be production eligible')
    else:
        child=terminal['child'];need(child['main_complete'] is True and child['science_complete'] is True and child['physical_usage']['training_steps']>=256,'public receipt lacks completed primary256 SFT')
        need(seal['solver_manifest_sha256']=='549019b4b5cb47176f3abd3fcd9ca516e91b7d6e581dfc414a5a6452ff7b1f7f' and seal['evaluator_manifest_sha256']=='c7e8ad35770a66a71a22cccbbd0455c1c3bcc1a505dfb2e4c29819eec6209e33','production public material identity differs')
        need(execution['production_eligible'] is (expected_complete and child.get('operational_success') is True and child.get('error') is None),'public production eligibility differs from actual child execution')
    need(all(type(execution.get(k)) is bool for k in ('production_eligible','complete','complete_coverage')) and type(summary.get('complete_official_pinned_set')) is bool,'exact public eligibility/coverage booleans required')
    need(summary['evidence_mode']==execution['evidence_mode'] and summary['frozen_method']==execution['method'],'public evidence mode/frozen method differs')
    if not synthetic:need(summary['evidence_mode']=='public-development' and terminal['child']['production_model'] is True,'nonproduction public receipt cannot claim production')
    eligible=bool(execution['production_eligible'] and execution['complete'] and execution['complete_coverage'] and summary['complete_official_pinned_set'] and not synthetic)
    need(summary['eligible_complete_production_public_measurement'] is eligible and summary['goal_met'] is (eligible and num>=151),'public goal promotion differs')
    need(summary['complete_prediction_coverage']==execution['complete_coverage'] and summary['observed_queries']==execution['observed_queries'] and summary['generation_calls']==execution['generation_calls'],'public complete167 coverage differs')
    if eligible:need(summary['observed_queries']==167 and summary['generation_calls']==334 and summary['evidence_mode']=='public-development','eligible measurement missing actual full167 production calls')
    need(summary['official_score'] is None and summary['generation_may_resume'] is False and summary['four_l4_executed'] is False and summary['fp8_executed'] is False,'unsupported official/device claim')
    return {'status':summary['status'],'micro_pass_at_2_count':num,'denominator':167,'goal_met':summary['goal_met'],
        'eligible_complete_production_public_measurement':eligible,'scorer_sha256':summary['scorer_sha256'],
        'qualification':'Source-bound original scorer rows and clean bounded CPU subprocess receipt after sealed predictions and closed model owner. This subprocess receipt is not independently mapped provider/session closure. Validator never opens public gold.'}


def validate_training(archive,ledger,request,*,complete):
    seen={}
    def visit(value):
        if type(value) is list:
            for x in value:visit(x)
        elif type(value) is dict:
            if 'event_id' in value and 'adam_step' in value and 'changed_adapter_tensors' in value:
                eid=value['event_id'];need(eid in ledger['events'] and ledger['events'][eid]['event']=='complete' and ledger['events'][eid]['amounts']=={'training_steps':1,'input_tokens':value['input_tokens']},'calibration optimizer physical receipt differs')
                need(value['finite_gradients'] is True and integer(value['changed_adapter_tensors'],1) and value['adapter_before_sha256']!=value['adapter_after_sha256'] and number(value['loss']),'calibration optimizer update invalid')
                if eid in seen:need(seen[eid]==value,'calibration update copy differs')
                seen[eid]=value
            if 'physical_event_id' in value and 'optimizer_steps' in value and 'attempted_microbatches' in value:
                eid=value['physical_event_id'];need(eid in ledger['events'],'training lacks physical ledger receipt')
                if eid in seen:need(seen[eid]==value,'training receipt copies differ')
                seen[eid]=value;event=ledger['events'][eid]
                need(event['amounts']=={'training_steps':value['attempted_microbatches'],'input_tokens':value['input_tokens']},'actual training work charge differs')
                need(integer(value['optimizer_steps']) and value['steps']==value['optimizer_steps'] and value['usage_known'] is True,'optimizer step/usage receipt differs')
                if value['status']=='complete':
                    need(event['event']=='complete' and value['optimizer_state_consistent'] is True and value['tiny_cpu'] is request['config'].get('tiny_cpu',False),'complete optimizer state/origin differs')
                    updates=value['updates'];need(len(updates)==value['optimizer_steps'],'optimizer update count differs')
                    prior=value['adapter_before_sha256'];last=None
                    for update in updates:
                        need(update['finite_gradients'] is True and integer(update['changed_adapter_tensors'],1) and number(update['gradient_norm']) and number(update['elapsed_seconds']) and number(update['loss']),'nonfinite/unchanged optimizer update')
                        need(update['adapter_before_sha256']==prior and hash_ok(update['adapter_after_sha256']) and update['adapter_after_sha256']!=prior,'adapter update chain differs')
                        need(integer(update['adam_step'],1) and (last is None or update['adam_step']==last+1),'Adam update sequence differs')
                        prior=update['adapter_after_sha256'];last=update['adam_step']
                    need(prior==value['adapter_after_sha256'],'final adapter update fingerprint differs')
            for x in value.values():visit(x)
    for name in archive.members:
        if name.endswith('.json') and 'target-escrow' not in name and '/upstream/data/evaluation/' not in name:visit(archive.json(name))
    expected={eid for eid,event in ledger['events'].items() if event.get('amounts',{}).get('training_steps',0)>0}
    need(not expected-set(seen),'physical training events lack durable actual receipts')
    if complete:
        updates=request['config'].get('test_checkpoint_updates',[1,2]) if request['config'].get('tiny_cpu') else [64,256];previous=0;prior=None
        for update in updates:
            row=archive.json('experiment/train-'+str(update)+'.json')
            need(row['status']=='complete' and row['optimizer_steps']==update-previous and row['requested_steps']==update-previous,'fixed SFT optimizer count differs')
            if prior:need(prior==row['adapter_before_sha256'],'global SFT state continuity differs')
            previous=update;prior=row['adapter_after_sha256']
    return {'durable_training_events':len(seen),'physical_training_microbatches':ledger['used']['training_steps'],'optimizer_steps':sum(r.get('optimizer_steps',1) for r in seen.values())}


def validate_score_receipts(archive,terminal):
    if 'main-scoring.json' not in archive.members:
        need(terminal['status']!='TRANSFER_COMPLETE','complete transfer missing closed main scoring');return None
    score=archive.json('main-scoring.json');need(terminal.get('main_scoring')==score,'terminal main scorer projection differs')
    need(score['format']=='irisx/transfer-after-owner-closure-scores-v1' and score['all_denominators_retained'] is True and score['model_owner_closed'] is True and score['public_score'] is None,'main score closure boundary differs')
    for scope,n in (('dev',16),('holdout',32)):
        rows=score['scopes'][scope]
        methods=archive.json('experiment/'+scope+'-predictions-sealed.json')['methods']
        need(set(rows)==set(methods)|{'selected_ttt_subset'},'closed scoring method set differs')
        for cid,row in rows.items():
            denominator=8 if cid=='selected_ttt_subset' else n
            need(row['denominator']==denominator and integer(row['pass_at_2_count'],0,denominator) and row['pass_at_2']==row['pass_at_2_count']/denominator,'main score denominator/arithmetic differs')
            need(all(integer(row[k],0,denominator) for k in ('valid_count','shape_correct_count','abstentions','paired_gains_vs_base','paired_losses_vs_base')) and row['valid_count']+row['abstentions']==denominator and row['pass_at_2_count']<=row['shape_correct_count']<=row['valid_count'],'main score count consistency differs')
            if 'pass_at_1_count' in row:need(integer(row['pass_at_1_count'],0,row['pass_at_2_count']) and row['pass_at_1']==row['pass_at_1_count']/denominator,'pass@1 score arithmetic differs')
        if scope=='dev' and 'experiment/frozen-selection.json' in archive.members:
            selection=archive.json('experiment/frozen-selection.json')
            for rank in selection['rankings']:
                row=rows[rank['candidate_id']];need((rank['exact'],rank['shape'],rank['valid'])==(row['pass_at_2_count'],row['shape_correct_count'],row['valid_count']),'dev selection and closed scorer receipt differ')
    return {'source_bound_runtime_scores_verified':True,'target_escrow_opened':False,'qualification':'Receipt arithmetic and sealed method denominators verified; no target escrow was parsed or rescored.'}


def validate_content(output_root,expected_source,*,source_root,allow_synthetic=False,verify_checkpoint_bytes=False):
    """Source-aware manual content subcheck. Does not assert provider admission."""
    root=Path(output_root);terminal=json_file(root/'terminal-receipt.json');archive=ClosedArchive(root/'evidence.zip')
    mapping=json_file(expected_source) if isinstance(expected_source,(str,Path)) else expected_source
    mapping=mapping.get('mapping',mapping.get('source_identity',mapping))
    source=SourceSnapshot(source_root,mapping)
    try:
        need(terminal['format']=='irisx/true-arc-transfer-owned-v1' and terminal['status'] in STATUSES,'unknown transfer terminal status')
        request=archive.json('request.json');child=archive.json('child-summary.json');tiny=request['config'].get('tiny_cpu',False)
        need(type(tiny) is bool and (not tiny or allow_synthetic),'synthetic fixture rejected by production API')
        source_archive_cap=load_helper('budget_checks').validate_source_policy(source,synthetic=tiny)
        need(source_archive_cap==512*1024**2,'checkpoint-repair source must retain512MiB aggregate cap')
        for key,kind in (('GLOBAL','global'),('FIXTURE','fixture'),('TTT','ttt')):
            need(source.assignment(CHECKPOINT_POLICY_MEMBER,key)==CHECKPOINT_SCHEDULES[kind][0],'source checkpoint schedule constant differs')
        need(sum(x.file_size for x in archive.members.values())<=source_archive_cap,'archive exceeds exact source aggregate capacity')
        need(request['format']=='irisx/true-arc-transfer-request-v1' and request['source_identity']==source.mapping,'exact source identity differs')
        need(terminal['source_identity_sha256']==child['source_identity_sha256']==digest(source.mapping) and child['request_sha256']==raw_sha(archive.read('request.json')),'terminal/source/request bindings differ')
        need(terminal['child']==child,'terminal child projection differs')
        need(terminal['archive']['sha256']==archive.sha256 and terminal['archive']['bytes']==(root/'evidence.zip').stat().st_size and terminal['archive']['files']==len(archive.members),'terminal archive receipt differs')
        clean=terminal['status']!='TRANSFER_FAILED';owned_tree(archive,'owned-tree/',terminal['closure_proof'],clean=clean)
        launch=archive.json('owned-tree/launch.json');argv=launch['worker_argv']
        need(argv[-2:]==[str(PurePosixPath(request['output_root'])/'request.json'),raw_sha(archive.read('request.json'))] and argv[-3].endswith('/'+PACKAGE+'child.py'),'model owner entrypoint/request differs')
        need(terminal['owned_process_closed'] is True and child['pending_work']=={} and child['model_stopped'] is True and child['child_cleanup_complete'] is True,'unclosed model owner or pending work')
        need(child['public_gold_opened'] is False,'model owner read public gold')
        need(terminal['science_complete'] is (terminal['status']=='TRANSFER_COMPLETE'),'terminal science completion flag differs')
        need(type(terminal['operational_success']) is bool and (not terminal['operational_success'] or terminal['science_complete'] and child.get('operational_success') is True),'operational/science status conflation')
        if not tiny:
            need(not any(k.startswith('test_') for k in request['config']),'test-only seam in production request')
            need(source.protocol.get('execution_cutoff_seconds')==42000 and source.protocol.get('provider_runtime_seconds')==42300,'source execution/provider cutoff differs')
        clocks=validate_clocks(request,terminal,synthetic=tiny)
        validate_phase_artifacts(archive,terminal)
        ledger=ledger_replay(archive.read('physical-work.jsonl'),require_closed=True)
        need(child['physical_usage']==ledger['used'],'terminal physical totals differ')
        result={'format':'irisx/true-arc-transfer-checkpoint-repair-content-validation-v1','valid':True,'status':terminal['status'],'synthetic':tiny,
            'provider_envelope_verified':False,'runtime_science_complete':terminal['science_complete'],'science_complete':not tiny and terminal['science_complete'],'operational_success':not tiny and terminal['operational_success'],
            'source_identity_sha256':digest(source.mapping),'source_archive_cap_bytes':source_archive_cap,'clock':clocks,'physical_usage':ledger['used'],'pending_work':ledger['pending'],
            'goal_met':False,'public_gold_opened_by_validator':False,'archive_sha256':archive.sha256}
        if clean:need(type(child.get('model_identity')) is dict and child.get('production_model') is (not tiny),'clean transfer lacks actual declared model origin')
        if child.get('model_identity'):
            result['model']=validate_model_identity(child['model_identity'],tiny,source=source,hardware=archive.json('model-admission.json')['hardware'])
            admission=archive.json('model-admission.json');ident={k:v for k,v in child['model_identity'].items() if k not in ('decoder_policy','decoder_policy_sha256')}
            need(admission['identity']==ident,'model admission/terminal identity differs')
        if 'dataset/solver-dataset.json' in archive.members:dataset=validate_panel(archive,synthetic=tiny)
        else:need(not clean,'clean transfer missing data panel');dataset=None
        if 'feasibility.json' in archive.members:result['costs']=validate_costs(archive,request,source,ledger,synthetic=tiny)
        if terminal['status']=='TRANSFER_NOT_ADMITTED':need(result.get('costs',{}).get('main_admitted') is False,'not-admitted status without denied admission')
        if terminal['status']=='TRANSFER_COMPLETE':
            need(child.get('main_complete') is True and all(n in archive.members for n in ('experiment/dev-prediction-seal.json','experiment/holdout-prediction-seal.json','experiment/main-complete.json','experiment/frozen-selection.json')),'complete transfer lacks actual sealed main panels')
            main=archive.json('experiment/main-complete.json');need(main['complete'] is True and main['selection']==child['selection'] and main['dev_seal']==child['dev_seal'] and main['holdout_seal']==child['holdout_seal'],'main-complete receipt differs')
        if 'experiment/holdout-prediction-seal.json' in archive.members:
            need(dataset is not None,'predictions missing dataset');validate_seals(archive,request,dataset,terminal)
            result['ttt']=validate_ttt(archive,request,dataset)
        result['training']=validate_training(archive,ledger,request,complete=terminal['status']=='TRANSFER_COMPLETE')
        result['main_scoring']=validate_score_receipts(archive,terminal)
        result['native_coverage']=native_coverage(archive,ledger,complete=terminal['status']=='TRANSFER_COMPLETE')
        result['call_budget']=load_helper('budget_checks').validate_calls(archive,request,ledger)
        result['checkpoints']=validate_checkpoints(root,archive,request,source,complete=terminal['status']=='TRANSFER_COMPLETE',verify_checkpoint_bytes=verify_checkpoint_bytes)
        result['public_evaluation']=validate_public(archive,request,terminal,source,synthetic=tiny)
        result['verified_measurement_goal_met']=result['public_evaluation']['goal_met']
        result['goal_met']=result['verified_measurement_goal_met'] and result['operational_success'] and result['science_complete']
        return result
    except (KeyError,TypeError,IndexError,AttributeError,ZeroDivisionError,ValueError) as exc:
        if isinstance(exc,ValidationError):raise
        raise ValidationError('malformed or incomplete transfer evidence: '+str(exc)) from exc
    finally:archive.close();source.close()


def document(value):
    if type(value) is dict:return deepcopy(value),digest(value)
    raw=local_file(value,16*1024**2).read_bytes();result=strict_json(raw,str(value));need(type(result) is dict,'object document required');return result,raw_sha(raw)


def normalize_notebook(value):
    value=deepcopy(value)
    need(type(value) is dict and type(value.get('cells')) is list,'notebook JSON required')
    for cell in value['cells']:
        if type(cell.get('source')) is list:cell['source']=''.join(cell['source'])
    return value


def notebook_constants(value):
    result={};counts={}
    for cell in value['cells']:
        if cell.get('cell_type')!='code':continue
        for node in ast.parse(cell['source']).body:
            if not isinstance(node,ast.Assign) or len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name):continue
            key=node.targets[0].id;counts[key]=counts.get(key,0)+1
            try:
                if key=='PINS' and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name) and node.value.func.value.id=='json' and node.value.func.attr=='loads' and len(node.value.args)==1:
                    result[key]=strict_json(ast.literal_eval(node.value.args[0]),'notebook PINS')
                else:result[key]=ast.literal_eval(node.value)
            except (ValueError,TypeError):pass
    need(counts.get('PREDISPATCH_EPOCH')==1,'one predispatch epoch assignment required')
    return result


def validate_launch(manifest,manifest_sha,finalization,journal,launch,finalized_notebook,manifest_root,*,allow_synthetic=False):
    need(manifest['format']=='irisx/qwen14b-transfer-checkpoint-repair-publication-contract-v1','successor publication contract required')
    contract=manifest['terminal_contract']
    expected_caps={'evidence_expanded_bytes':512*1024**2,'evidence_archive_bytes':544*1024**2,'evidence_members':12000,'checkpoint_expanded_bytes':2*1024**3,'checkpoint_archive_bytes':2*1024**3+2*1024**2,'checkpoint_members':1025}
    need(contract['archive_caps']==expected_caps,'exact generation-repair archive capacities differ')
    expected_members={'terminal-receipt.json':1024**2,'launcher/result.json':1024**2,'ordinary_evidence_member':16*1024**2,'large_diagnostic_member':64*1024**2,'checkpoint_member':32*1024**2}
    need(contract['file_byte_caps']==expected_members and set(contract['large_diagnostic_paths'])==LARGE,'exact per-member evidence caps differ')
    need(contract['active_role']=='transfer003','terminal contract active role differs')
    specs=[n for n in manifest['notebooks'] if n['role']=='transfer003'];need(len(specs)==1,'exact transfer003 active role required');spec=specs[0]
    need(spec['output_root']=='/kaggle/working/irisx-qwen14b-transfer-20261012-run003' and spec['source_parent']=='/kaggle/working/irisx-qwen14b-transfer-20261012-source003','checkpoint-repair run/source identity differs')
    need(spec['existing_notebook_id']==138123872 and type(spec['expected_version']) is int and spec['expected_version']==25 and type(spec['expected_predecessor_version']) is int and spec['expected_predecessor_version']==24,'new notebook numeric identity differs')
    codes=[d for d in manifest['datasets'] if d['role']=='code'];need(len(codes)==1 and type(codes[0]['expected_version']) is int and codes[0]['expected_version']==13 and codes[0]['id']==12504696,'new code13 identity differs')
    policy_ref=manifest['generation_call_policy'];policy_raw=local_file(manifest_root/safe_name(policy_ref['path']),1024**2).read_bytes();policy_doc=strict_json(policy_raw)
    helper=load_helper('budget_checks');source_mapping=manifest['terminal_contract']['inner_request_source_identity']['mapping']
    need(len(policy_raw)==policy_ref['bytes'] and raw_sha(policy_raw)==policy_ref['sha256'],'generation policy artifact bytes differ')
    need(policy_doc['format']=='irisx/transfer002-source-bound-generation-policy-v1' and policy_doc['runtime_policy']==helper.POLICY and policy_doc['runtime_policy_sha256']==policy_ref['runtime_policy_sha256']==digest(helper.POLICY),'generation policy descriptor differs')
    need(policy_doc['source_member']==policy_ref['source_member']==PACKAGE+'call_policy.py' and policy_doc['source_sha256']==policy_ref['source_sha256']==source_mapping[PACKAGE+'call_policy.py'],'generation policy exact source binding differs')
    need(policy_doc['timing_refresh_source_member']==PACKAGE+'timing_refresh.py' and policy_doc['timing_refresh_source_sha256']==source_mapping[PACKAGE+'timing_refresh.py'],'timing refresh source descriptor differs')
    expected_policy={'generation_hard_seconds':180,'generation_work_seconds':175,'likelihood_hard_seconds':120,'likelihood_work_seconds':115,'execution_cutoff_seconds':42000,'outer_cutoff_seconds':42180,'provider_runtime_seconds':42300,'global_seconds':43200,'scientific_model_material_panels_scoring_unchanged':True,'forecast_is_guarantee':False}
    need(all(type(policy_doc.get(k)) is type(value) and policy_doc[k]==value for k,value in expected_policy.items()),'generation policy declared bounds differ')
    checkpoint_ref=manifest['checkpoint_policy'];checkpoint_raw=local_file(manifest_root/safe_name(checkpoint_ref['path']),1024**2).read_bytes()
    need(len(checkpoint_raw)==checkpoint_ref['bytes'] and raw_sha(checkpoint_raw)==checkpoint_ref['sha256'],'checkpoint policy descriptor bytes differ')
    checkpoint_doc=strict_json(checkpoint_raw)
    # PROTOCOL is unchanged scientifically, and the exact declared policy hash
    # is checked again against source bytes by validate_content.
    protocol_sha=checkpoint_doc['contracts']['global']['protocol_sha256']
    expected_contracts={}
    for kind,(sid,branch,scope,updates,fixture) in CHECKPOINT_SCHEDULES.items():
        expected_contracts[kind]={'format':'irisx/transfer-checkpoint-schedule-v1','schedule_id':sid,'scope':scope,
            'allowed_updates':updates,'fixture_only':fixture,'branch_id':branch,'protocol_sha256':protocol_sha,
            'source_sha256':{name:source_mapping[PACKAGE+name] for name in ('checkpoint_policy.py','protocol.py')}}
    expected_checkpoint={'format':'irisx/transfer003-source-bound-checkpoint-policy-v1','contracts':expected_contracts,
        'source_sha256':{name:source_mapping[name] for name in (CHECKPOINT_POLICY_MEMBER,PACKAGE+'protocol.py',CHECKPOINT_MEMBER)}}
    need(hash_ok(protocol_sha) and exact(checkpoint_doc,expected_checkpoint),'checkpoint policy source-bound contracts differ')
    if not allow_synthetic:
        need(manifest.get('release_runtime_finalized') is True and manifest.get('source_review_only') is False,'unreviewed preview cannot validate production envelope')
        approval_ref=manifest['runtime_source_approval'];approval_path=manifest_root/safe_name(approval_ref['path']);approval_raw=local_file(approval_path,4*1024**2).read_bytes()
        need(raw_sha(approval_raw)==approval_ref['sha256'] and len(approval_raw)==approval_ref['bytes'],'exact independent runtime approval differs')
        approval=strict_json(approval_raw);need(approval['format']=='irisx/independent-transfer-checkpoint-runtime-review-v1' and approval['approved'] is True and approval['known_blockers']==[],'independent runtime source approval missing')
        mapping=manifest['terminal_contract']['inner_request_source_identity']['mapping']
        need(all(mapping.get(k)==value for k,value in approval['runtime_source_identity'].items() if PurePosixPath(k).suffix in ('.py','.json','.jinja')),'runtime approval does not bind exact released source')
    raw=local_file(finalized_notebook,4*1024**2).read_bytes();template_raw=local_file(manifest_root/safe_name(spec['path']),4*1024**2).read_bytes()
    need(raw_sha(raw)==finalization['finalized_sha256']==launch['submitted_source_sha256']==journal['source_sha256'],'finalized/submitted notebook bytes differ')
    need(raw_sha(template_raw)==spec['sha256']==finalization['template_sha256'],'exact notebook template differs')
    for receipt in (journal,launch):need(receipt['manifest_sha256']==manifest_sha,'launch/publication manifest differs')
    if 'manifest_sha256' in finalization:need(finalization['manifest_sha256']==manifest_sha,'finalization/publication manifest differs')
    epoch=finalization['predispatch_epoch'];need(number(epoch,1),'finite positive original dispatch epoch required')
    expected={'deadline_epoch':epoch+43200,'global_deadline_epoch':epoch+43200,'execution_deadline_epoch':epoch+42000,'outer_deadline_epoch':epoch+42180,'provider_timeout_seconds':42300}
    for key,value in expected.items():need(finalization[key]==value and journal[key]==value,'same-origin clock envelope differs: '+key)
    need(journal['predispatch_epoch']==epoch and number(journal['dispatch_epoch']) and 0<=journal['dispatch_epoch']-epoch<=60,'stale/refreshed dispatch epoch')
    notebook=normalize_notebook(strict_json(raw));template=normalize_notebook(strict_json(template_raw));patch=spec['dispatch_epoch_patch']
    need(patch['assignment']=='PREDISPATCH_EPOCH' and patch['maximum_patch_age_seconds']==60 and patch['maximum_changed_assignments']==1 and patch['required_original_value'] is None,'JIT epoch patch policy differs')
    index=patch['cell_index'];code=notebook['cells'][index]['source'];pattern=r'(?m)^PREDISPATCH_EPOCH\s*=\s*([^\n]+)$';found=re.findall(pattern,code)
    need(len(found)==1 and type(ast.literal_eval(found[0])) in (int,float) and ast.literal_eval(found[0])==epoch,'notebook epoch assignment differs')
    reset=deepcopy(notebook);reset['cells'][index]['source']=re.sub(pattern,'PREDISPATCH_EPOCH = None',code)
    need(reset==template,'non-epoch finalized notebook mutation')
    saved=launch['saved_source'];saved_raw=local_file(saved['path'],4*1024**2).read_bytes()
    need(raw_sha(saved_raw)==saved['sha256'] and len(saved_raw)==saved['bytes'] and normalize_notebook(strict_json(saved_raw))==notebook and launch['normalized_source_exact'] is True,'provider saved notebook differs')
    reference=spec['existing_notebook_reference']
    need(journal['reference']==launch['reference']==reference and journal['kernel_id']==launch['kernel_id']==138123872 and type(launch['version']) is int and launch['version']==journal['expected_version']==25 and type(journal['save_calls']) is int and journal['save_calls']==1,'single exact active save identity differs')
    need(journal.get('role')=='transfer003','exact checkpoint-repair journal role required')
    constants=notebook_constants(notebook)
    need(constants.get('PREDISPATCH_EPOCH')==epoch and constants.get('MANUAL_START') is True and constants.get('ENABLE_MODEL') is True and constants.get('PROFILE')=='QWEN14B_TRANSFER12H' and constants.get('SESSION_SECONDS')==constants.get('PROBE_SECONDS')==43200,'active transfer notebook configuration differs')
    need(constants['OUTPUT_ROOT']==spec['output_root'] and constants['SOURCE_PARENT']==spec['source_parent'],'transfer output/source identity differs')
    need(spec['provider_runtime_seconds']==42300 and spec['execution_cutoff_seconds']==42000 and spec['outer_cutoff_seconds']==42180 and spec['program_session_seconds']==spec['global_seconds']==43200,'provider/program/inner clock contract differs')
    return spec,constants


class Downloads:
    def __init__(self,root,receipt,launch,spec,manifest_sha):
        self.root=Path(root).absolute();self.files={};self.listed={}
        need(receipt.get('format')=='irisx/transfer-selected-retrieval-v1','selected numeric retrieval format required')
        need(self.root.is_dir() and not any(p.is_symlink() for p in (self.root,*self.root.parents)),'regular download root required')
        need(receipt['numeric_output_version']==25 and type(receipt['numeric_output_version']) is int and receipt['manifest_sha256']==manifest_sha and receipt['reference']==launch['reference'] and receipt['kernel_id']==138123872,'retrieval identity differs')
        need(receipt.get('inventory_scope')=='selected_outputs_only' and receipt.get('whole_provider_inventory_verified') is False and receipt.get('provider_files_scope')=='selected_numeric_byte_or_header_facts','selected provider evidence inventory scope differs')
        terminal_statuses={'COMPLETE','ERROR','CANCELLED','CANCELED','CANCEL_ACKNOWLEDGED'}
        for key in ('before','after'):
            snap=receipt[key];need(type(snap['version']) is int and snap['version']==25 and snap['status'] in terminal_statuses and snap['source_sha256']==launch['saved_source']['sha256'] and hash_ok(snap['metadata_sha256']),'provider version/source/status bracket differs')
        need(receipt['before']['status']==receipt['after']['status'],'provider status changed during retrieval')
        need(type(receipt['files']) is list and 0<len(receipt['files'])<=12000,'retrieval file count invalid')
        total=0;locals_seen=set()
        for row in receipt['files']:
            name=safe_name(row['provider_path']);local=safe_name(row['local_path'])
            need(name not in self.files and local not in locals_seen,'duplicate provider/local download')
            need(type(row['version']) is int and type(row['numeric_version']) is int and row['version']==row['numeric_version']==25 and row['http_status']==200 and row['source_kind'] in ('provider_download','sealed_archive_member'),'retrieval provenance/version differs')
            cap=544*1024**2 if name.endswith('/evidence.zip') else 2*1024**3+2*1024**2 if name.endswith('/checkpoints.zip') else 1024**2 if name.endswith('/terminal-receipt.json') or name.endswith('-launcher/result.json') else 4*1024**2
            path=local_file(self.root/local,cap);need(path.stat().st_size==row['bytes'] and file_sha(path)==row['sha256'],'retrieval actual bytes differ')
            total+=row['bytes'];need(total<=2624*1024**2,'download aggregate cap')
            self.files[name]=(path,row);locals_seen.add(local)
        need(type(receipt['provider_files']) is list and len(receipt['provider_files'])<=20000,'bounded exact provider inventory required')
        for row in receipt['provider_files']:
            name=safe_name(row['path']);need(name not in self.listed and integer(row['bytes']) and type(row.get('numeric_version')) is int and row['numeric_version']==25 and row.get('size_source') in ('verified_numeric_download','numeric_response_header_only'),'invalid selected provider byte fact');self.listed[name]=row['bytes']
            if row['size_source']=='verified_numeric_download':need(name in self.files and self.files[name][1]['source_kind']=='provider_download' and self.files[name][1]['bytes']==row['bytes'],'provider byte fact lacks actual matching download')
            else:need(name==PurePosixPath(spec['output_root']).name+'/checkpoints.zip','header-only fact outside checkpoint archive')
        for name,(_,row) in self.files.items():
            if row['source_kind']=='provider_download':need(self.listed.get(name)==row['bytes'],'download/provider listing size differs')
            else:
                archive_path=safe_name(row['archive_provider_path']);need(archive_path in self.files,'derived download lacks original archive')
                path,descriptor=self.files[archive_path];need(row['archive_sha256']==descriptor['sha256'],'derived archive identity differs')
                with zipfile.ZipFile(path) as z:need(raw_sha(z.read(safe_name(row['member_path'])))==row['sha256'],'derived member bytes differ')
    def raw(self,name):need(name in self.files,'missing required provider file: '+name);return self.files[name][0].read_bytes()
    def json(self,name):return strict_json(self.raw(name),name)


def validate_outer(downloads,spec,constants,finalization,terminal):
    prefix=PurePosixPath(spec['output_root']).name+'-launcher/';request_raw=downloads.raw(prefix+'request.json');request=strict_json(request_raw);outer=downloads.json(prefix+'launcher-closure.json')
    epoch=finalization['predispatch_epoch'];clean=terminal['status']!='TRANSFER_FAILED';proof=outer['process_tree_proof']
    need(outer['format']=='irisx/learning-notebook-closure-v1' and outer['started_epoch']==epoch and outer['hard_deadline_epoch']==epoch+42180 and outer['global_deadline_epoch']==epoch+43200,'outer original clock binding differs')
    need(request['started_epoch']==epoch and request['hard_deadline_epoch']==epoch+42180 and request['global_deadline_epoch']==epoch+43200 and request['execution_deadline_epoch']==epoch+42000 and request['provider_deadline_epoch']==epoch+42300,'outer request clock allocation differs')
    need(number(outer['completed_epoch']) and epoch<=outer['completed_epoch']<=epoch+42180 and outer['within_absolute_deadline'] is True,'outer closure missed provider-safe deadline')
    if clean:need(outer['forced'] is False and outer['reason'] is None,'clean runtime with forced outer owner')
    class Adapter:
        def json(self,name):return downloads.json(prefix+name)
    owned_tree(Adapter(),'owned-tree/',proof,clean=clean)
    launch=downloads.json(prefix+'owned-tree/launch.json');worker=downloads.json(prefix+'owned-tree/worker-launch.json')
    need(launch['worker_argv'][-2:]==[str(PurePosixPath(request['launcher_root'])/'request.json'),raw_sha(request_raw)],'outer argv/request binding differs')
    expected_config={k.lower():constants[k] for k in ('MANUAL_START','ENABLE_MODEL','PROFILE','OUTPUT_ROOT','SOURCE_PARENT','INPUT_ROOT','CODE_ROOT','DATA_ROOT','TRAINING_ROOT')}
    expected_config.update(session_seconds=43200,probe_seconds=43200,predispatch_epoch=epoch)
    for key in ('execution_cutoff_seconds','outer_cutoff_seconds','provider_runtime_seconds'):
        need(constants[key.upper()]==spec[key],'outer notebook cutoff differs from manifest: '+key)
        expected_config[key]=constants[key.upper()]
    need(len(expected_config)==15 and exact(request['config'],expected_config) and exact(request['pins'],constants['PINS']),'outer config/PINS differ from submitted notebook')
    need(request['loader_sha256']==constants['EXPECTED_LOADER_SHA256']==raw_sha(constants['LOADER_SOURCE'].encode()) and request['guard_sha256']==constants['EXPECTED_GUARD_SHA256']==raw_sha(constants['GUARD_SOURCE'].encode()),'outer loader/guard source differs')
    need(downloads.raw(prefix+'owned_process_guard.py')==constants['GUARD_SOURCE'].encode(),'actual outer process guard bytes differ')
    need(downloads.json(prefix+'result.json')==terminal,'outer/inner terminal result differs')
    return {'launcher_closure_sha256':raw_sha(downloads.raw(prefix+'launcher-closure.json')),'outer_worker_identity':worker['worker_identity'],'completed_epoch':outer['completed_epoch']}



def validate_checkpoint_observation(retrieval,terminal,downloads,prefix,*,bytes_verified):
    name=prefix+'checkpoints.zip';actual=name in downloads.files;declared=terminal.get('checkpoint_archive')
    need(type(retrieval.get('checkpoint_downloaded')) is bool and retrieval['checkpoint_downloaded'] is actual,'checkpoint download flag differs from actual evidence')
    if actual:
        need(bytes_verified is True and declared is not None,'checkpoint bytes supplied without complete byte verification')
        return 'VERIFIED_ARCHIVE_BYTES'
    need(bytes_verified is False,'metadata-only checkpoint promoted to byte verification')
    observed=retrieval.get('checkpoint_metadata_only')
    need(type(observed) is dict and observed.get('path')==name and observed.get('body_consumed_bytes')==0 and type(observed.get('body_consumed_bytes')) is int and observed.get('archive_bytes_verified') is False,'checkpoint metadata-only scope differs')
    if declared:
        need(observed.get('presence')=='HTTP200_CONTENT_LENGTH_VERIFIED' and type(observed.get('http_status')) is int and observed['http_status']==200 and integer(observed.get('bytes'),0,2*1024**3+2*1024**2) and observed['bytes']==declared['bytes'] and downloads.listed.get(name)==declared['bytes'],'declared checkpoint numeric header/size evidence differs')
        need(observed.get('declared_sha256_unverified')==declared['sha256'] and observed.get('scope')=='numeric output request; Content-Length and successful response only','header-only checkpoint hash/scope conflated')
        rows=[r for r in retrieval['provider_files'] if r['path']==name]
        need(len(rows)==1 and rows[0].get('size_source')=='numeric_response_header_only' and rows[0].get('numeric_version')==25,'checkpoint header fact provenance differs')
        return 'HTTP200_CONTENT_LENGTH_VERIFIED'
    need(observed.get('presence')=='UNKNOWN' and observed.get('bytes') is None and name not in downloads.listed,'undeclared checkpoint must stay unknown')
    return 'UNKNOWN'

def validate_outputs(download_root,*,manifest,finalization,launch_journal,launch_receipt,retrieval_receipt,finalized_notebook,allow_synthetic=False):
    """Collector API. No provider call, code execution, gold read or model download."""
    need(type(allow_synthetic) is bool,'explicit Boolean synthetic option required')
    need(isinstance(manifest,(str,Path)),'exact reviewed publication manifest path required')
    m,msha=document(manifest);f,fsha=document(finalization);j,jsha=document(launch_journal);l,lsha=document(launch_receipt);r,rsha=document(retrieval_receipt);base=Path(manifest).absolute().parent
    try:
        synthetic=any(x.get('synthetic') is True for x in (f,j,l,r))
        need(not synthetic or allow_synthetic,'synthetic envelope denied in production API')
        if allow_synthetic:need(all(x.get('synthetic') is True for x in (f,j,l,r)),'all synthetic envelopes must be explicit')
        need(l['launch_journal_sha256']==jsha and l['finalization_sha256']==fsha and r['launch_receipt_sha256']==lsha,'launch/retrieval receipt hash chain differs')
        spec,constants=validate_launch(m,msha,f,j,l,finalized_notebook,base,allow_synthetic=allow_synthetic)
        d=Downloads(download_root,r,l,spec,msha);prefix=PurePosixPath(spec['output_root']).name+'/'
        need(prefix+'terminal-receipt.json' in d.files and prefix+'evidence.zip' in d.files,'required transfer outputs missing')
        out=d.files[prefix+'terminal-receipt.json'][0].parent
        need(d.files[prefix+'evidence.zip'][0].parent==out,'terminal and archive download roots differ')
        inner=m['terminal_contract']['inner_request_source_identity'];mapping=inner['mapping']
        need(digest(mapping)==inner['identity_sha256'],'manifest inner source commitment differs')
        codes=[x for x in m['datasets'] if x['role']=='code'];code=codes[0];source_zip=base/safe_name(code['payload_root'])/'source.zip'
        zip_entry=[x for x in code['upload_inventory'] if x['path']=='source.zip'];need(len(zip_entry)==1 and file_sha(local_file(source_zip,64*1024**2))==zip_entry[0]['sha256'],'exact approved source ZIP differs')
        snapshot=SourceSnapshot(source_zip,mapping)
        try:
            descriptor=json_file(base/safe_name(m['checkpoint_policy']['path']))
            need(exact(descriptor['contracts'],{kind:checkpoint_contract(snapshot,kind) for kind in CHECKPOINT_SCHEDULES}),
                 'publication checkpoint schedule protocol/source differs from actual source ZIP')
        finally:snapshot.close()
        result=validate_content(out,mapping,source_root=source_zip,allow_synthetic=allow_synthetic,verify_checkpoint_bytes=prefix+'checkpoints.zip' in d.files)
        need(result['synthetic'] is synthetic,'envelope/runtime synthetic origin differs')
        terminal=json_file(out/'terminal-receipt.json');outer=validate_outer(d,spec,constants,f,terminal)
        need(result['clock']['started_epoch']==f['predispatch_epoch'],'inner predispatch clock reset')
        with zipfile.ZipFile(out/'evidence.zip') as archive:
            launch=strict_json(archive.read('owned-tree/launch.json'))
            if not synthetic:need(strict_json(archive.read('request.json'))['output_root']==spec['output_root'],'actual model output root differs from release role')
            a=launch['coordinator_identity'];b=outer['outer_worker_identity'];need(a['pid']==b['pid'] and a['birth']==b['birth'],'inner/outer ownership incarnation differs')
        for name,item in m['terminal_contract']['outer_executable_files'].items():
            raw=d.raw(PurePosixPath(spec['output_root']).name+'-launcher/'+name);need(raw_sha(raw)==item['sha256'] and len(raw)==item['bytes'],'outer executable source differs')
        checkpoint_presence=validate_checkpoint_observation(r,terminal,d,prefix,bytes_verified=result['checkpoints']['verified_archive_bytes'])
        if r['before']['status']!='COMPLETE':
            result['verified_runtime_operational_success']=result['operational_success']
            result['operational_success']=False;result['goal_met']=False
        result.update(format='irisx/true-arc-transfer-checkpoint-repair-terminal-validation-v1',provider_envelope_verified=True,reference=l['reference'],kernel_id=138123872,version=25,
            manifest_sha256=msha,retrieval_receipt_sha256=rsha,finalized_source_sha256=f['finalized_sha256'],saved_source_sha256=l['saved_source']['sha256'],
            launcher_closure_sha256=outer['launcher_closure_sha256'],provider_status=r['before']['status'],provider_vm_or_billing_state_verified=False,
            checkpoint_archive_bytes_verified=result['checkpoints']['verified_archive_bytes'],inventory_scope='selected_outputs_only',whole_provider_inventory_verified=False,separate_checkpoint_presence=checkpoint_presence)
        return result
    except (KeyError,TypeError,IndexError,AttributeError,SyntaxError,ValueError,OSError,zipfile.BadZipFile) as exc:
        if isinstance(exc,ValidationError):raise
        raise ValidationError('malformed or incomplete successor collector envelope: '+str(exc)) from exc


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-root',required=True)
    for key in ('manifest','finalization','launch-journal','launch-receipt','retrieval-receipt','finalized-notebook'):parser.add_argument('--'+key,required=True)
    args=vars(parser.parse_args(argv));root=args.pop('download_root');args['retrieval_receipt']=json_file(args['retrieval_receipt'])
    try:result=validate_outputs(root,**args)
    except ValidationError as exc:print(json.dumps({'status':'REJECTED','valid':False,'operational_success':False,'goal_met':False,'error':str(exc)},sort_keys=True));return 2
    print(json.dumps(result,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
