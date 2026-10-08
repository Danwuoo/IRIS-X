"""Owner-started uncapped runtime. No provider actions and no resource ceiling.

Physical RAM, disk and Kaggle session/quota limits still apply. The scientific
workload remains a native 128-row TTT epoch followed by the declared search.
"""
from __future__ import annotations
import argparse
import copy
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time

from tools.nvarc_native_multitask import canonical, digest, require, public_training_material
from tools.nvarc_uncapped_artifacts import atomic_json as write, read_json as _read, sha_file, full_diagnostic as diagnostic, StreamEvents, cleanup_workers, owned_process_state, register_worker
from tools.nvarc_native_submission import reject_truth

from tools.nvarc_e10_probe import verify_observations
from tools.nvarc_e11_paired_floor import verify_model_metadata
from tools import nvarc_e10_end_to_end as native_epoch
from tools import nvarc_e10_ttt_probe as native_training
from tools.nvarc_native_solve_runtime import compare_vectors
from tools.nvarc_e12_training import PROFILES
from tools import nvarc_e12_prefix_contract as prefix

FORMAT = 'irisx/stage4-uncapped-owner-editor-v1'
RUN_ID = 'stage4-uncapped-20261008-001'
CONFIG_NAME = 'CONFIRM_UNCAPPED_OWNER_RUN'
CONFIRMATION_FILE = 'owner-start-confirmation.json'


def binding(plan, rank):
    return dict(probe_id=plan['run_id'], plan_digest=digest(plan), rank=rank,
        task_id=plan['task_order'][rank], model_material_digest=plan['model_material_digest'])


def verify_plan(plan):
    require(plan.get('format') == FORMAT and plan.get('run_id') == plan.get('screen_id') == RUN_ID,
        'exact separate uncapped identity required')
    require(plan.get('kernel_execution_type') == 'QUICK_SAVE' and
        plan.get('owner_editor_only') is True and plan.get('agent_execution_authorized') is False and
        plan.get('approved_for_runtime') is False and plan.get('resource_admission') is None and
        plan.get('paid_usd_ceiling') == 0 and plan.get('official_submission') is False,
        'manual owner-only private free QuickSave contract required')
    require(plan.get('resource_policy') == 'no-program-capacity-or-time-caps' and
        all(plan.get(k) is None for k in plan['removed_resource_caps']),
        'no artificial resource ceilings permitted')
    require(plan.get('scientific_contract') == {
        'training_updates_per_task':128, 'training_epochs':1, 'test_cases':6,
        'searches_per_test':1, 'dfs_probability_floor':.2,
        'verification_schedule':'interleaved', 'source_views':16,
        'source_batch_size':4, 'verification_views':8,
        'grid_max_rows':30, 'grid_max_columns':30, 'answer_grammar_tokens':931,
        'model_context_tokens':8192, 'displayed_guesses':2},
        'unchanged finite scientific workload and grammar required')
    require(plan.get('test_counts') == {'195c6913':2,'aa4ec2a5':1,'a47bf94d':1,'a25697e4':2}
        and plan.get('task_order') == ['195c6913','aa4ec2a5','a47bf94d','a25697e4'],
        'same four exposed tasks and six tests required')
    reject_truth(plan)
    return plan


def verify_runtime(root, expected_plan_sha256, *, confirmed=False):
    root=Path(root)
    require(root.is_dir() and not any(p.is_symlink() for p in (root,*root.parents)), 'regular runtime root required')
    raw=(root/'plan.json').read_bytes(); plan=verify_plan(json.loads(raw))
    require(raw == canonical(plan) == (root/'screen.json').read_bytes() and
        hashlib.sha256(raw).hexdigest() == expected_plan_sha256, 'trusted exact plan pin required')
    for name, expected in plan['payload_sha256'].items():
        path=root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
            path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)) and
            path.resolve().is_relative_to(root.resolve()) and sha_file(path)==expected,
            'immutable runtime material/source differs: '+name)
    if confirmed:
        require(plan.get('scientific_design_confirmed') is True, 'experimental design must be owner-confirmed')
        receipt=_read(root/CONFIRMATION_FILE)
        require(receipt.get('format')=='irisx/uncapped-owner-start-v1' and receipt.get('run_id')==RUN_ID and
            receipt.get('plan_digest')==digest(plan) and receipt.get('confirmed') is True and
            receipt.get('paid_scaling_off_declared') is True and receipt.get('manual_only') is True,
            'actual explicit owner confirmation required')
    return plan


def write_confirmation(root,plan,confirmed):
    require(type(confirmed) is bool and confirmed is True, 'owner must explicitly set the visible boolean')
    path=Path(root)/CONFIRMATION_FILE
    require(not path.exists(), 'one owner start per distinct runtime identity')
    write(path,dict(format='irisx/uncapped-owner-start-v1',run_id=RUN_ID,plan_digest=digest(plan),
        confirmed=True,manual_only=True,paid_scaling_off_declared=True,started_monotonic=time.monotonic(),
        declared_platform_quota_checked=True,resource_sufficiency_verified=False,
        warning='No program runtime or storage ceiling; actual platform limits remain. Owner stops the session.'))


def verify_dependency(root,plan,dependency):
    """Exact provenance lengths are identity checks, never an artificial read cap."""
    from tools.nvarc_dependency_readproof import RECEIPT_FORMAT, LIMITATIONS, SELECTED_PATHS
    dependency=Path(dependency); proof=_read(Path(root)/'dependency-readproof.json')
    require(digest(proof)==plan['dependency_readproof_digest'] and set(proof['selected_files'])==SELECTED_PATHS,
        'same pinned selected dependency bytes required')
    started=time.monotonic(); observed={}
    for name, expected in sorted(proof['selected_files'].items()):
        path=dependency/name
        require(path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)) and
            stat.S_ISREG(path.stat().st_mode) and path.stat().st_nlink==1,
            'regular exact dependency file required')
        row=dict(bytes=path.stat().st_size,sha256=sha_file(path))
        require(row==expected, 'pinned dependency differs: '+name);observed[name]=row
    receipt=dict(format=RECEIPT_FORMAT,outcome='verified-selected-bytes',plan_digest=digest(plan),
        contract_digest=digest(proof),dependency_root=os.path.abspath(dependency),selected_files=observed,
        file_bytes_read=sum(r['bytes'] for r in observed.values()),elapsed_host_seconds=time.monotonic()-started,
        error=None,limitations=LIMITATIONS,discovered_code_executions=0,model_calls=0,
        resource_limits_applied=False)
    write(Path(root)/'dependency-readproof-receipt.json',receipt)
    return sha_file(Path(root)/'dependency-readproof-receipt.json')


def verify_dependency_receipt(root,plan,dependency,expected):
    path=Path(root)/'dependency-readproof-receipt.json';r=_read(path)
    require(sha_file(path)==expected and r['plan_digest']==digest(plan) and
        r['contract_digest']==plan['dependency_readproof_digest'] and
        r['dependency_root']==os.path.abspath(dependency) and r['outcome']=='verified-selected-bytes' and
        r['selected_files']==_read(Path(root)/'dependency-readproof.json')['selected_files'],
        'hash-bound parent dependency receipt required')


def prepare(root,plan,dependency):
    require(sys.version_info[:3]==(3,11,13), 'same pinned Python 3.11.13 required')
    inventory=_read(root/'source-inventory.json')
    for name,item in inventory.items():
        path=dependency/name
        require(path.stat().st_size==item['bytes'] and sha_file(path)==item['sha256'], 'dependency source differs: '+name)
    write(root/'source-verification.json',dict(inventory_digest=digest(inventory),dependency_root=str(dependency)))
    sys.path.insert(0,str(dependency))
    import torch
    from hardware_helpers import collect_hardware_inventory
    require(torch.__version__=='2.8.0+cu128' and torch.version.cuda=='12.8' and
        Path(torch.__file__).resolve().is_relative_to(dependency.resolve()), 'same pinned Torch/CUDA required')
    smi=subprocess.run(['nvidia-smi','--query-gpu=index,name,memory.total,uuid','--format=csv,noheader,nounits'],
        capture_output=True,text=True,check=True)
    hardware=collect_hardware_inventory(torch,smi.stdout,lambda value:write(root/'hardware-raw.json',value))
    require(len(hardware)==len({r['uuid'] for r in hardware})==4 and
        all(r['name']=='NVIDIA L4' and r['bf16'] for r in hardware),'same four distinct BF16 L4 devices required')
    write(root/'hardware.json',dict(inventory=hardware,torch=torch.__version__,cuda=torch.version.cuda))
    mounts=[Path('/kaggle/input/models/sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'),
        Path('/kaggle/input/qwen3_4b_grids15_sft139/transformers/bfloat16/1')]
    matches=[p for p in mounts if (p/'config.json').is_file()]
    require(len(matches)==1,'one exact unchanged model mount required');model=matches[0]
    for name,item in _read(root/'model-inventory.json').items():
        path=model/name
        require(path.stat().st_size==item['bytes'] and sha_file(path)==item['sha256'],'pinned model differs: '+name)
    write(root/'model-verification.json',dict(model_material_digest=plan['model_material_digest'],all_ten_files_verified=True,competition_files_opened=0))
    with (root/'dependency-setup.log').open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-m','pip','uninstall','-y','tensorflow'],stdout=log,stderr=subprocess.STDOUT,check=True)
    return model,hardware


def training_sources(plan,key):
    return dict(challenge_digest=plan['challenges_digest'],model_digest=plan['model_material_digest'],
        dependency_digest=plan['dependency_readproof_digest'],configuration_digest=digest(plan['original_training_arguments']),
        inference_contract_digest=digest(plan['scientific_contract']),native_sampler_digest='sha256:'+'0'*64)


def inference_transition(engine, trainer, output, bound, phase):
    """Retain success or failure; no extra control, generation, or verifier calls."""
    receipt = {'format':'irisx/native-inference-transition-v1','binding':bound,'phase':phase,
        'status':'failed','before':None,'after':None,'model_identity_preserved':False,
        'parameters_preserved':False,'model_forwards':0,'errors':[]}
    model = engine.model
    def parameters():
        return [(id(p),str(p.dtype),str(p.device),tuple(p.shape),
            p.data_ptr(),p._version) for p in model.parameters()]
    try:
        receipt['before'] = native_epoch.forward_observation(model); before_parameters = parameters()
        native_epoch.unwrap_training_forward(model,trainer)
        engine.inference()
        receipt['after'] = native_epoch.forward_observation(engine.model)
        receipt['model_identity_preserved'] = engine.model is model
        receipt['parameters_preserved'] = parameters() == before_parameters
        require(receipt['model_identity_preserved'] and receipt['parameters_preserved'] and
            receipt['after']['training'] is False and receipt['after']['fp32_wrapper_count'] == 0 and
            receipt['after']['original_forward_present'] is False,
            'same model/parameter storage/dtype/version and unwrapped eval forward required')
        receipt['status'] = 'complete'
    except BaseException as error:
        receipt['errors'].append(diagnostic(error,'native-inference-transition'))
        raise
    finally:
        write(output/(phase+'-inference-transition.json'),receipt)
    return receipt



def completed_training_updates(budget):
    """Count only durable completed optimizer returns, including failed epochs."""
    if budget is None:return 0
    return sum(row.get('completed') is True for row in budget.state['optimizer_steps'])


def worker(root,dependency,model,rank,parent_pid,receipt_sha,expected_plan_sha256):
    from tools.nvarc_public_eval import install_owner_guard, PhaseTelemetry
    from tools.nvarc_public_eval_runtime import NativeEngine
    from tools.nvarc_e10_probe import control_adapter, verify_observations
    from tools.nvarc_e10_paired_schedule import capture_rng,restore_rng,model_metadata
    from tools.nvarc_e11_paired_floor import verify_model_metadata
    from tools import nvarc_e10_end_to_end as native_epoch
    from tools import nvarc_e10_ttt_probe as native_training
    from tools.nvarc_native_ttt_schedule import native_schedule
    from tools.nvarc_uncapped_training import PrefixBudget,rng_observation
    from tools.nvarc_native_solve_runtime import discard_optimizer_state,reset_control
    from tools import nvarc_uncapped_inference as inference
    root=Path(root);plan=verify_runtime(root,expected_plan_sha256,confirmed=True)
    install_owner_guard(parent_pid,signal.SIGKILL)
    output=root/'workers'/str(rank);train=output/'training';key=plan['task_order'][rank];bound=binding(plan,rank)
    events=StreamEvents(output/'events.jsonl',bound);observed=[];adapters=[];telemetry=PhaseTelemetry()
    errors=[];engine=trainer=budget=None;baseline=trained=None;completed=0;epoch_complete=False;initialization_attempted=False;answers=None;reset=None
    def emit(event,**details):
        observed.append(dict(event=event,**details));verify_observations(observed);events.emit(event,**details)
    class Engine(NativeEngine):
        def adapter(self,_emit,tests=1):
            value=control_adapter(self.model,self.torch,emit,telemetry);adapters.append(value);return value
    started=time.monotonic();trace_complete=optimizer_discarded=restored_ok=False
    try:
        verify_dependency_receipt(root,plan,dependency,receipt_sha)
        initialization_attempted=True
        with telemetry.scope('load'):engine=Engine(root,plan,model,dependency,rank)
        require(len(adapters)==1,'one resident model and six semantic initialization controls required')
        baseline=engine.inventory();write(output/'baseline-inventory.json',baseline)
        write(output/'cache-control.json',engine.initial_control)
        base_metadata=model_metadata(engine.model);verify_model_metadata(base_metadata,plan)
        write(output/'baseline-model-metadata.json',base_metadata)
        ready=_read(output/'ready.json');ready['binding']=bound;write(output/'ready.json',ready)
        common_rng=capture_rng(engine);blocked=[]
        with telemetry.scope('preparation'),native_training.preparation_guard(engine.torch,blocked.append) as guard:
            material=public_training_material(engine.loader,engine.tokenizer,key,_read(root/'challenges.json')[key])
            require(material==_read(root/'materials'/f'{key}.json'),'exact original128 public demonstration rows required')
            write(output/'texts.json',material['texts']);write(output/'expected-rows.json',material['rows']);guard()
        require(not blocked,'unexpected native work during preparation')
        train.mkdir();write(train/'baseline-inventory.json',baseline);restore_rng(engine,common_rng);blocked=[]
        with native_training.preparation_guard(engine.torch,blocked.append) as guard:
            trainer=engine.trainer(material['texts'],material['rows'],train)
            rates,schedule=native_schedule(engine.dependency,trainer.args,plan['native_source_learning_rates'])
            write(train/'native-schedule.json',schedule);guard()
        require(not blocked,'unexpected work during native Trainer preparation')
        write(output/'training-ready.json',dict(binding=bound,prepared_rows=128,prepared_rows_digest=digest(material['rows']),
            control_forwards=6,training_updates=0))
        while not (root/'training-release.json').is_file():time.sleep(.05)
        release=_read(root/'training-release.json')
        require(release['plan_digest']==digest(plan) and release['ranks']==[0,1,2,3], 'all-four unchanged preparation barrier required')
        require(engine.inventory()==baseline,'native epoch must start at unchanged baseline')
        before=model_metadata(engine.model);unchanged_model_layout(base_metadata,before,plan)
        write(train/'training-before-metadata.json',before)
        budget=PrefixBudget(engine,trainer,material['rows'],rates,schedule,plan['native_source_learning_rates'],train,training_sources(plan,key),'ttt128')
        training_started=time.monotonic()
        with telemetry.scope('training'),budget.installed():trainer.train();moments=budget.complete()
        completed=128;epoch_complete=True;write(train/'optimizer-state.json',moments)
        write(train/'training-observation.json',dict(updates=completed,elapsed_host_seconds=time.monotonic()-training_started,time_cap=None))
        trained=engine.inventory();require(native_training.changed_tensors(baseline,trained)>0,'adapted saved tensors must change')
        write(train/'trained-inventory.json',trained)
        after=model_metadata(engine.model);write(train/'training-after-metadata.json',after);unchanged_model_layout(before,after,plan)
        post_state=capture_rng(engine);write(train/'post-training-rng.json',rng_observation(post_state))
        discard_optimizer_state(engine.model,trainer,budget)
        require(optimizer_disposed(engine,trainer,budget),'discard Adam and gradients before search')
        optimizer_discarded=True;inference_transition(engine,trainer,train,bound,'trained')
        engine.torch.cuda.empty_cache();gc.collect()
        inference_dir=output/'inference';inference_dir.mkdir()
        before_inference=model_metadata(engine.model);write(inference_dir/'model-before-metadata.json',before_inference)
        write(inference_dir/'trained-before-inventory.json',engine.inventory())
        answers=inference.solve_task(engine,root,plan,rank,telemetry,directory=inference_dir)
        write(inference_dir/'trained-after-inventory.json',engine.inventory())
        after_inference=model_metadata(engine.model);write(inference_dir/'model-after-metadata.json',after_inference)
        require(engine.inventory()==trained and before_inference==after_inference,'search must not mutate trained model')
        restore_rng(engine,post_state)
    except BaseException as error:errors.append(diagnostic(error,'uncapped-worker'))
    finally:
        if engine is not None:
            def attempt(action,phase):
                try:return action()
                except BaseException as error:errors.append(diagnostic(error,phase));return None
            if trainer is not None:attempt(lambda:discard_optimizer_state(engine.model,trainer,budget),'discard')
            optimizer_discarded=optimizer_disposed(engine,trainer,budget)
            attempt(engine.restore,'restore')
            if train.is_dir():attempt(lambda:inference_transition(engine,trainer,train,bound,'reset'),'reset-inference')
            else:attempt(engine.inference,'reset-inference')
            restored=attempt(engine.inventory,'reset-inventory');restored_ok=restored==baseline
            attempt(lambda:write(output/'final-reset-inventory.json',restored),'reset-write')
            if train.is_dir():attempt(lambda:write(train/'reset-inventory.json',restored),'training-reset-write')
            if budget is not None and epoch_complete and restored_ok:
                trace_complete=attempt(budget.finish,'trace-finish') is not None
            reset=attempt(lambda:reset_control(adapters[0],engine.initial_control),'reset-control')
            if reset is not None:attempt(lambda:write(output/'post-reset-control.json',reset),'reset-control-write')
        completed=completed_training_updates(budget)
        value=dict(binding=bound,outcome='failed' if errors else 'complete',errors=errors,
            completed_training_updates=completed,full_epoch_verified=epoch_complete,trace_complete=trace_complete,baseline_restored=restored_ok,
            optimizer_discarded=optimizer_discarded,controls=verify_observations(observed),post_reset_control=reset,
            elapsed_host_seconds=time.monotonic()-started,peak_host_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            peak_cuda_allocated_bytes=None if engine is None else engine.torch.cuda.max_memory_allocated(),
            native_model_instances=(None if initialization_attempted else 0) if engine is None else 1,
            native_initialization_attempted=initialization_attempted,resource_limits_applied=False,telemetry=telemetry.snapshot(),
            correctness_scored=False,promotion=False)
        write(output/'result.json',value)
        events.close()
    return 1 if errors else 0


# Retained scientific proof checks; reads have no artificial size ceiling.
def unchanged_model_layout(before,after,plan):
    # Training is intentional; require complete 905 metadata and frozen tensor
    # versions/storage unchanged. All 506 adapted bytes are separately hashed.
    for value in (before,after):
        projected=copy.deepcopy(value);projected['training']=False
        verify_model_metadata(projected,plan)
    require(before['model_identity']==after['model_identity'] and before['buffers']==after['buffers'] and
        before['rotary_caches']==after['rotary_caches'],'resident model and complete cache/buffer identity required')
    for a,b in zip(before['parameters'],after['parameters']):
        require({k:v for k,v in a.items() if k!='version'}=={k:v for k,v in b.items() if k!='version'} and
            (a['requires_grad'] or a==b),'frozen model parameter metadata mutated during adaptation')


def optimizer_disposed(engine,trainer,budget):
    return (trainer is None or trainer.optimizer is trainer.lr_scheduler is None and
        not trainer.accelerator._optimizers and not trainer.accelerator._schedulers and
        (budget is None or budget.optimizer is None)) and all(p.grad is None for p in engine.model.parameters())



def verify_controls(directory,result,bound):
    def read(name):return _read(directory/name)
    observed = []; head = digest(bound); body = (directory/'events.jsonl').read_bytes()
    require(body.endswith(b'\n'), 'complete control event chain required')
    for i,line in enumerate(body.splitlines()):
        row = json.loads(line)
        require(all(row[k] == v for k,v in bound.items()) and type(row['rank']) is type(row['sequence']) is int and
            row['sequence'] == i and row['previous'] == head and
            row['digest'] == digest({k:v for k,v in row.items() if k != 'digest'}), 'control event chain differs')
        head = row['digest']; observed.append(row)
    require([r['event'] for r in observed] == ['forward_reserved','forward_completed']*6+
        ['cache_control_result','forward_reserved','forward_completed'] and
        result['controls'] == verify_observations(observed) == {
            'reserved_forwards':7,'completed_forwards':7,'reserved_physical_input_tokens':168}, 'exact seven controls required')
    reservations = [r for r in observed if r['event'] == 'forward_reserved']
    completions = [r for r in observed if r['event'] == 'forward_completed']
    for i,(width,cached,start) in enumerate(((9,False,0),(1,True,9),(1,True,10),(1,True,9),
            (11,False,0),(10,False,0),(9,False,0))):
        r = reservations[i]
        require(all(type(r[k]) is int for k in ('call_id','physical_input_tokens','position_start','position_end')) and
            all(type(v) is int for v in r['batch_shape']) and
            r['call_id'] == i+1 and r['batch_shape'] == [4,width] and r['physical_input_tokens'] == 4*width and
            r['cached'] is cached and r['position_start'] == start and r['position_end'] == start+width-1,
            'exact cache/reset synthetic sequence required')
        require(type(completions[i]['call_id']) is int and completions[i]['call_id'] == i+1 and
            completions[i]['output_contract'] in ('tuple-logits-cache','model-output-logits-cache'),
            'exact completed synthetic forward required')
    cache = observed[12]; comparisons = {'deep':compare_vectors(cache['deep_reference'],cache['deep_cached']),
        'sibling_after_deep':compare_vectors(cache['sibling_reference'],cache['sibling_cached'])}
    reset = read('post-reset-control.json')
    vectors = [cache[k] for k in ('baseline_prefill','deep_reference','deep_cached','sibling_reference','sibling_cached')]
    vectors.append(reset['prefill'])
    require(all(type(v) is list and len(v) == 4 and all(type(row) is list and len(row) == 16 and
        all(type(x) in (int,float) and math.isfinite(x) for x in row) for row in v) for v in vectors) and
        all(r['prefill_bitwise_equal'] is True and r['synthetic_tokens_only'] is True and
            type(r['additional_model_calls']) is int and r['additional_model_calls'] == 1
            for r in (reset,result['post_reset_control'])),
        'finite complete synthetic vectors and strict reset flags required')
    require(cache['comparisons'] == comparisons and all(v['gate_passed'] for v in comparisons.values()) and
        reset == result['post_reset_control'] == {'prefill_bitwise_equal':True,'prefill':cache['baseline_prefill'],
            'synthetic_tokens_only':True,'additional_model_calls':1}, 'actual cache and seventh reset control required')
    return result['controls']



def verify_training(root,plan,rank):
    arm_id='ttt128'
    directory=Path(root)/'workers'/str(rank)/'training'
    read=lambda name:_read(directory/name)
    key=plan['task_order'][rank];spec=plan['task_specs'][key];limit=128
    material=_read(Path(root)/'materials'/f'{key}.json');contract=read('prefix-contract.json');trace=read('prefix-trace.json')
    prefix.validate_trace(contract,trace)
    require(contract['evidence_kind']=='native-observed' and trace['profile']==PROFILES[arm_id] and
        contract['prepared_rows']==[{k:r[k] for k in prefix.ROW_FIELDS} for r in material['rows']] and
        len(material['rows'])==len(material['texts'])==128 and digest(material['rows'])==spec['expected_rows_digest'] and
        digest(material['texts'])==spec['texts_digest'],'exact native-prepared source rows and128horizon contract required')
    schedule=read('native-schedule.json');sampler=read('sampler.json')
    require(set(sampler)=={'module','name','source_path','source_sha256','iterator_source_path','iterator_source_sha256','replacement','num_samples','order'} and
        (sampler['module'],sampler['name'],sampler['source_path']) in
            {('torch.utils.data.sampler','RandomSampler','torch/utils/data/sampler.py'),
             ('accelerate.data_loader','SeedableRandomSampler','accelerate/data_loader.py')} and
        sampler['iterator_source_path']=='torch/utils/data/sampler.py' and
        type(sampler['iterator_source_sha256']) is str and len(sampler['iterator_source_sha256'])==64 and
        all(c in '0123456789abcdef' for c in sampler['iterator_source_sha256']) and type(sampler['source_sha256']) is str and
        len(sampler['source_sha256'])==64 and all(c in '0123456789abcdef' for c in sampler['source_sha256']) and
        sampler['replacement'] is False and type(sampler['num_samples']) is int and sampler['num_samples']==128 and
        sampler['order']==contract['sampler_order'],'observed unchanged native full sampler required')
    sources=training_sources(plan,key);sources['native_sampler_digest']=digest({k:v for k,v in sampler.items() if k!='order'})
    expected=prefix.build_native_contract(rows=contract['prepared_rows'],sampler_order=sampler['order'],
        reset=contract['reset'],sources=sources,rates=schedule['rates'],reference_rates=plan['native_source_learning_rates'],
        schedule_receipt=schedule)
    require(expected==contract,'native schedule/source provenance differs from trusted caller plan')
    ledger=read('training-ledger.json')
    require(set(ledger)=={'forwards','training_steps','optimizer_steps','optimizer_constructions','generation_calls','teacher_calls'} and
        ledger['optimizer_constructions']==[{'completed':True}] and
        type(ledger['generation_calls']) is type(ledger['teacher_calls']) is int and
        ledger['generation_calls']==ledger['teacher_calls']==0 and
        all(type(ledger[k]) is list and len(ledger[k])==limit for k in ('forwards','training_steps','optimizer_steps')),
        'one optimizer and exact completed E13 full128 counters required')
    for i,event in enumerate(trace['steps']):
        forward=ledger['forwards'][i];step=ledger['optimizer_steps'][i]
        require(set(forward)==prefix.ROW_FIELDS|{'completed','loss'} and
            {k:forward[k] for k in prefix.ROW_FIELDS}==event['row'] and forward['loss']==event['loss'] and
            forward['completed'] is True and ledger['training_steps'][i]=={'completed':True} and
            set(step)=={'learning_rate','gradient_tensors','gradient_norm_after_clip','completed'} and
            step['completed'] is True and step['learning_rate']==contract['learning_rates'][i] and
            type(step['gradient_tensors']) is int and step['gradient_tensors']==506 and
            type(step['gradient_norm_after_clip']) in (float,int) and math.isfinite(step['gradient_norm_after_clip']) and
            0<=step['gradient_norm_after_clip']<=1.05,'actual native forward/backward/Adam ledger differs from prefix trace')
    moments=read('optimizer-state.json')
    require(type(moments) is list and len(moments)==506 and sum(r['elements'] for r in moments)==528564224 and
        all(set(r)=={'elements','parameter_dtype','parameter_device','moment_bytes','step','finite'} and
            type(r['step']) is type(r['elements']) is type(r['moment_bytes']) is int and r['step']==limit and
            r['elements']>0 and r['moment_bytes']==4*r['elements'] and r['finite'] is True and
            r['parameter_dtype']=='torch.bfloat16' and r['parameter_device']=='cuda:0' for r in moments),
        'all506 finite native Adam states including zero-LR update required')
    status=read('native-hook-status.json')
    require(status==dict(format='irisx/e12-native-hooks-v1',arm_id=arm_id,sampler_iterations=1,callback_steps=limit,errors=[]),
        'all actual callback/sampler hooks must complete without failure')
    preparation=read('preparation.json')
    require(preparation==dict(checkpoint_flags=plan['native_checkpoint_flags'],trainer_origins=plan['native_trainer_origins']),
        'pinned native original Trainer and checkpoint policy required')
    prepared=read('prepared-rows.json')
    require(type(prepared) is list and len(prepared)==128 and all(
        set(r)==prefix.ROW_FIELDS|{'row','collator_preserved_input_ids','source_input_ids_equal','source_labels_equal'} and
        type(r['row']) is int and r['row']==i and {k:r[k] for k in prefix.ROW_FIELDS}==contract['prepared_rows'][i] and
        r['source_input_ids_equal'] is r['source_labels_equal'] is r['collator_preserved_input_ids'] is True
        for i,r in enumerate(prepared)), 'all128 actual prepared collator row/label digests required')
    baseline=read('baseline-inventory.json');trained=read('trained-inventory.json');restored=read('reset-inventory.json')
    require(baseline==restored==_read(Path(root)/'workers'/str(rank)/'baseline-inventory.json') and
        contract['reset']['model_inventory_digest']==digest(baseline) and
        native_training.changed_tensors(baseline,trained)>0 and
        all(r['finite'] is True and r['dtype']=='torch.bfloat16' for inv in (baseline,trained,restored) for r in inv),
        'exact baseline/changed506trained/reset bytes required')
    unchanged_model_layout(read('training-before-metadata.json'),read('training-after-metadata.json'),plan)
    for phase in ('trained','reset'):
        native_epoch.verify_inference_transition(read(phase+'-inference-transition.json'),binding(plan,rank),phase)
    return contract,trace




def verify_worker_result(root,plan,rank,uuid):
    from tools import nvarc_uncapped_inference as inference
    directory=Path(root)/'workers'/str(rank);result=_read(directory/'result.json');bound=binding(plan,rank)
    require(result['binding']==bound and result['outcome']=='complete' and result['errors']==[] and
        result['completed_training_updates']==128 and result['full_epoch_verified'] is True and result['trace_complete'] is result['baseline_restored'] is
        result['optimizer_discarded'] is True and result['native_model_instances']==1 and
        result['resource_limits_applied'] is result['correctness_scored'] is result['promotion'] is False,
        'one complete native128 worker with reset proof required')
    ready=_read(directory/'ready.json')
    require(ready['uuid']==uuid and ready['rank']==rank and ready['binding']==bound,'assigned GPU and task binding required')
    verify_controls(directory,result,bound);verify_training(root,plan,rank)
    before=_read(directory/'inference/model-before-metadata.json');after=_read(directory/'inference/model-after-metadata.json')
    verify_model_metadata(before,plan);require(before==after,'unchanged trained inference metadata required')
    require(_read(directory/'inference/trained-before-inventory.json')==_read(directory/'inference/trained-after-inventory.json')==
        _read(directory/'training/trained-inventory.json'),'one unchanged post-TTT model for search required')
    answers=inference.verify_task(root,plan,rank,directory=directory/'inference')
    return dict(result,verified_inference=answers)


def execute(root,dependency,owner_pid,expected_plan_sha256):
    from tools.nvarc_public_eval import install_owner_guard
    from tools.nvarc_resource_attachment import verify_mount
    SCOPE='frozen public solver-visible development challenges only'
    root=Path(root);dependency=Path(dependency);started=time.monotonic()
    install_owner_guard(owner_pid,signal.SIGTERM)
    def cancelled(*_):raise KeyboardInterrupt('owner/session cancellation')
    signal.signal(signal.SIGTERM,cancelled)
    plan=verify_runtime(root,expected_plan_sha256,confirmed=True)
    states=[];results={};errors=[];cleanup=None
    try:
        receipt_sha=verify_dependency(root,plan,dependency)
        write(root/'mount-policy.json',verify_mount(plan,SCOPE));model,hardware=prepare(root,plan,dependency)
        for rank in range(4):
            directory=root/'workers'/str(rank);directory.mkdir(parents=True,exist_ok=False)
            state=dict(identity=str(rank),process=None,start_new_session=True,streams={});states.append(state)
            for kind in ('stdout','stderr'):state['streams'][kind]=(directory/(kind+'.log')).open('wb')
            env=dict(os.environ,PYTHONHASHSEED='0',CUDA_VISIBLE_DEVICES=hardware[rank]['uuid'],
                PYTHONPATH=str(root)+os.pathsep+str(dependency),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                HF_DATASETS_OFFLINE='1',UNSLOTH_DISABLE_STATISTICS='1',WANDB_DISABLED='true',OMP_NUM_THREADS='2',
                MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',PYTHONIOENCODING='utf-8',
                TRITON_CACHE_DIR=str(directory/'triton-cache'),TRITON_PTXAS_PATH='/usr/local/cuda/bin/ptxas')
            command=[sys.executable,str(root/'tools/nvarc_uncapped_entry.py'),'--root',str(root),'--dependency',str(dependency),
                '--model',str(model),'--rank',str(rank),'--parent-pid',str(os.getpid()),
                '--dependency-receipt-sha256',receipt_sha,'--expected-plan-sha256',expected_plan_sha256]
            state['process']=subprocess.Popen(command,env=env,cwd=directory,start_new_session=True,
                stdout=state['streams']['stdout'],stderr=state['streams']['stderr'])
            owned=owned_process_state(state['process'],str(rank));state.update(owned);register_worker(state)
            pid=state['process'].pid
            write(directory/'process-launch.json',dict(format='irisx/uncapped-owned-worker-v1',binding=binding(plan,rank),
                pid=pid,process_group_id=pid,start_new_session=True,parent_pid=os.getpid(),
                proc_starttime=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]))
        ready={}
        while len(ready)<4:
            for rank,state in enumerate(states):
                require(state['process'].poll() is None,'worker stopped before all-four native preparation barrier')
                path=root/'workers'/str(rank)/'training-ready.json'
                if path.is_file():
                    row=_read(path);spec=plan['task_specs'][plan['task_order'][rank]]
                    require(row==dict(binding=binding(plan,rank),prepared_rows=128,prepared_rows_digest=spec['expected_rows_digest'],
                        control_forwards=6,training_updates=0),'exact prepared native training barrier required')
                    ready[str(rank)]=row
            if len(ready)<4:time.sleep(.05)
        write(root/'training-release.json',dict(plan_digest=digest(plan),ranks=[0,1,2,3],ready=ready,release_monotonic=time.monotonic()))
        while any(s['process'].poll() is None for s in states):
            require(not any(s['process'].poll() not in (None,0) for s in states),'worker failure; stop remaining workers without retry')
            time.sleep(.1)
        for rank,state in enumerate(states):
            require(state['process'].returncode==0,'worker failed: '+str(rank))
            results[str(rank)]=verify_worker_result(root,plan,rank,hardware[rank]['uuid'])
        require(sum(r['completed_training_updates'] for r in results.values())==512,'all four original128 epochs required')
    except BaseException as error:errors.append(diagnostic(error,'uncapped-coordinator'))
    finally:
        try:
            cleanup=cleanup_workers([s for s in states if s['process'] is not None])
            require(cleanup.get('all_producers_stopped') is True,'all owned producers must be stopped')
        except BaseException as error:errors.append(diagnostic(error,'uncapped-cleanup'))
        for state in states:
            for stream in state['streams'].values():
                try:
                    if not stream.closed:stream.flush();os.fsync(stream.fileno());stream.close()
                except BaseException as error:errors.append(diagnostic(error,'worker-log-close'))
    terminal=dict(format='irisx/uncapped-terminal-v1',run_id=RUN_ID,plan_digest=digest(plan),
        outcome='failed' if errors else 'complete',errors=errors,results=results,cleanup=cleanup,
        elapsed_host_seconds=time.monotonic()-started,resource_limits_applied=False,
        actual_platform_limits_remain=True,correctness_scored=False,promotion=False,official_submission=False,paid_usd=0)
    write(root/'terminal.json',terminal)
    print(json.dumps(dict(run_id=RUN_ID,outcome=terminal['outcome'],completed_workers=len(results),errors=len(errors))),flush=True)
    return 1 if errors else 0
