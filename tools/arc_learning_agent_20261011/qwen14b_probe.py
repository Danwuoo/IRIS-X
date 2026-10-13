"""Default-off owned-process first capability probe, never public inference.

No reviewed deployment is shipped. Once separately reviewed exact material and
first-probe hardware bindings exist, this launcher may load once under a hard
<=1800s budget, measure the actual authored workload, and close the entire tree.
Only completed exact-length rungs are reported measured; no public admission follows.
"""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import sys
import time
from .budget import atomic_json
from .qwen14b_profiles import require
from .qwen14b_admission import select_reviewed_deployment


def run_owned_probe(config, output, *, maximum_seconds=1800):
    """Explicit opt-in with guarded closure; no environment/weights downloaded."""
    select_reviewed_deployment(config)
    require(type(maximum_seconds) is int and 30<=maximum_seconds<=1800,'bounded capability probe deadline required')
    root=Path(output).absolute();root.mkdir(parents=True,exist_ok=False)
    began=time.monotonic();hard=began+maximum_seconds
    request={'model_config':dict(config),'output_root':str(root),'work_deadline':hard-10}
    atomic_json(root/'request.json',request,exclusive=True)
    from . import process_guard as pg
    guard=None;proof=None;error=None;timed_out=False
    cwd=Path(__file__).resolve().parents[2]
    with (root/'bounded-process.log').open('xb') as log:
        try:
            guard=pg.OwnedProcessGuard.spawn([sys.executable,'-m','tools.arc_learning_agent_20261011.qwen14b_probe',
                '--child',str(root/'request.json')],evidence_dir=root/'owned-tree',cwd=str(cwd),stdout=log,stderr=log)
            while guard.poll() is None:
                if time.monotonic()>=hard-5:
                    timed_out=True;break
                if (root/'bounded-process.log').stat().st_size>1024**2:
                    raise RuntimeError('capability probe process output exceeded1MiB')
                time.sleep(0.05)
        except BaseException as exc:
            error=type(exc).__name__+': '+str(exc)[:512]
        finally:
            if guard is not None:
                try:
                    try:
                        proof=guard.closed_proof()
                    except BaseException:
                        proof=None
                    if not proof or not proof.get('closed'):proof=guard.stop(timeout=5)
                    pg.verify_closed_proof(proof)
                except BaseException as exc:
                    error='owned closure failure: '+str(exc)[:512]
    child=None
    path=root/'child-observation.json'
    if path.is_file() and not path.is_symlink() and path.stat().st_size<=1024**2:
        child=json.loads(path.read_bytes())
    clean=bool(proof and proof.get('closed') and proof.get('returncode')==0 and proof.get('worker_returncode')==0 and not proof.get('forced'))
    receipt={'format':'irisx/qwen14b-owned-capability-observation-v1','status':'observed' if clean and child and not error and not timed_out else 'failed',
             'child_observation':child,'owned_process_closed':bool(proof and proof.get('closed')),'closure_proof':proof,
             'error':error,'timed_out':timed_out,'elapsed_seconds':time.monotonic()-began,'maximum_seconds':maximum_seconds,
             'public_solving_admitted':False,'public_answers_used':False,'production_admitted':False,
             'independently_reviewed':False,'automatic_promotion':False,'fp8_executed':False,'tensor_parallel_size':1}
    atomic_json(root/'probe-observation.json',receipt,exclusive=True)
    return receipt


def prepare_length_control(native, length):
    """Author-written valid identity program with comments; exact native length.

    Synthetic repeated prompt words/comment tokens are a memory stress fixture,
    not ARC data or a learnability benchmark. No truncation or token padding is
    hidden in a mask. Every target is native-template-derived text plus EOS.
    """
    require(type(length) is int and length in (128,512,2048),'reviewed fixed length ladder only')
    completion_tokens = {128:16,512:64,2048:256}[length]
    prompt_tokens = length-completion_tokens
    tokenizer=native.tokenizer
    def program(n):
        return 'def transform(grid):\n    #'+' x'*n+'\n    return grid'
    minimum=program(0)
    n=completion_tokens-1-len(tokenizer.encode(minimum,add_special_tokens=False))
    completions=[program(i) for i in range(max(0,n-4),max(0,n)+5)]
    completion=next((v for v in completions if len(tokenizer.encode(v,add_special_tokens=False))+1==completion_tokens),None)
    require(completion is not None,'native completion cannot represent exact ladder target')
    def prompt_count(content):
        messages=[{'role':'user','content':content}]
        text=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        return len(tokenizer.encode(text,add_special_tokens=False))
    n=prompt_tokens-prompt_count('x')
    candidates=['x '*i+'x' for i in range(max(0,n-4),max(0,n)+5)]
    content=next((v for v in candidates if prompt_count(v)==prompt_tokens),None)
    require(content is not None,'native prompt cannot represent exact ladder target')
    row=native.prepare_completion([{'role':'user','content':content}],completion)
    native.validate_prepared(row)
    require(row['input_tokens']==length and row['prompt_tokens']==prompt_tokens and
            row['completion_tokens']==completion_tokens,'whole native ladder row identity differs')
    return row


def measure_cache_parity(model, ledger, messages, *, event_prefix, deadline, atol, rtol):
    """Three actual full-head forwards, each physically counted before dispatch."""
    require(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=0.01 for v in (atol,rtol)),
            'explicit independently reviewed finite cache tolerances required')
    import torch
    _,prompt=model._prompt(messages)
    raw=model.model;device=next(raw.parameters()).device;old_training=raw.training
    raw.eval()
    def forward(suffix,mask_length,past,index,use_cache):
        require(time.monotonic()<deadline,'deadline before native cache probe forward')
        event=event_prefix+'-'+str(index)
        ledger.reserve(event,{'scoring_forwards':1,'input_tokens':len(suffix)})
        try:
            result=raw(input_ids=torch.tensor([suffix],dtype=torch.long,device=device),
                attention_mask=torch.ones((1,mask_length),dtype=torch.long,device=device),past_key_values=past,
                use_cache=use_cache,logits_to_keep=1)
        except BaseException:
            ledger.complete(event,{'scoring_forwards':1,'input_tokens':len(suffix)},status='failed')
            raise
        ledger.complete(event,{'scoring_forwards':1,'input_tokens':len(suffix)})
        require(time.monotonic()<deadline,'cache probe forward completed after deadline')
        require(result.logits.shape[-1]==151936 and bool(torch.isfinite(result.logits).all()),
                'finite full native head required for cache comparison')
        return result
    try:
        with torch.inference_mode():
            prefill=forward(prompt,len(prompt),None,0,True)
            require(prefill.past_key_values is not None,'native cache missing')
            token=int(prefill.logits[0,-1].argmax())
            cached=forward([token],len(prompt)+1,prefill.past_key_values,1,True).logits[0,-1].float()
            full=forward(prompt+[token],len(prompt)+1,None,2,False).logits[0,-1].float()
            return {'passed':bool(torch.allclose(cached,full,atol=atol,rtol=rtol)),
                    'max_abs_error':float((cached-full).abs().max()),'atol':atol,'rtol':rtol,
                    'full_vocabulary_rows':151936,'physical_forwards':3,'physical_input_tokens':2*len(prompt)+2,
                    'cache_scope':'single-call disposable native cache'}
    finally:
        raw.train(old_training)


def _child(request):
    """Internal child. Author-written controls are code-bound, not public data."""
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2))
    root=Path(request['output_root']);deadline=request['work_deadline']
    require(time.monotonic()<deadline,'probe deadline expired before child bootstrap')
    config={**request['model_config'],'do_sample':False,'_owned_probe_deadline':deadline,
            '_owned_probe_supervisor_pid':os.getppid(),'_owned_probe_scope':'qwen14b-capability-only'}
    reviewed=select_reviewed_deployment(config)
    require(reviewed.get('length_ladder')==[128,512,2048] and reviewed.get('updates_per_rung')==1,
            'exact independently reviewed one-update length ladder required')
    from .qwen14b_backend import create_backend
    from .budget import WorkLedger
    from .data import create_split_manifest
    from .grid_codec import grid_messages
    tasks={'authored-train':{'train':[{'input':[[1,2]],'output':[[2,1]]},{'input':[[3,4]],'output':[[4,3]]}]},
           'authored-dev':{'train':[{'input':[[1],[2]],'output':[[1,1],[2,2]]},{'input':[[3]],'output':[[3,3]]}]}}
    manifest=create_split_manifest(tasks,fixed_splits={'train':['authored-train'],'dev':['authored-dev']})
    ledger=WorkLedger(root/'physical-work.jsonl')
    model,trainer=create_backend(config,{'split_manifest':manifest,'gradient_checkpointing':True,'seed':19},ledger=ledger)
    import torch
    start=time.monotonic();initial=trainer.snapshot('probe-initial');fingerprint=trainer.fingerprint()
    prompt=grid_messages(tasks['authored-train']['train'],[[5,6]])
    def behavior():
        generation=model.generate(prompt,kind='grid',seed=0,max_new_tokens=16,deadline=deadline)
        score=model.score_completion(prompt,'65',deadline=deadline)
        return {'generation':generation,'teacher_forced_score':score,
                'exact_authored_query':generation.get('valid') is True and generation.get('text')=='65'}
    observations=[];error=None;raw=trainer.trainer
    load_peak=int(torch.cuda.max_memory_allocated(0))
    try:
        for length in (128,512,2048):
            require(time.monotonic()<deadline,'length-ladder deadline expired')
            free,_=torch.cuda.mem_get_info(0)
            require(free>=reviewed['free_memory_reserve_bytes'],'reserved device memory unavailable before next rung')
            trainer.restore(initial)
            row=prepare_length_control(model,length)
            torch.cuda.reset_peak_memory_stats(0)
            with model.adapter_branch('base'):
                baseline=behavior()
                baseline['cached_full_parity']=measure_cache_parity(model,ledger,prompt,
                    event_prefix='cache-base-'+str(length),deadline=deadline,atol=reviewed['cache_atol'],rtol=reviewed['cache_rtol'])
                require(baseline['cached_full_parity']['passed'],'frozen-base native cache parity failed')
            event='length-control-'+str(length)
            ledger.reserve(event,{'training_steps':1,'input_tokens':length})
            update=None;reset=None;after=None;restored=None
            rung_started=time.monotonic()
            try:
                require(time.monotonic()<deadline,'deadline before stress backward')
                raw._make_optimizer()
                # Deliberate synthetic stress microbatch through the exact real
                # Trainer update primitive; not a global-training data record.
                update=raw._step(row)
                ledger.complete(event,{'training_steps':1,'input_tokens':length})
                require(time.monotonic()<deadline,'stress backward completed after deadline')
                after=behavior()
                after['cached_full_parity']=measure_cache_parity(model,ledger,prompt,
                    event_prefix='cache-updated-'+str(length),deadline=deadline,atol=reviewed['cache_atol'],rtol=reviewed['cache_rtol'])
                require(after['cached_full_parity']['passed'],'updated native cache parity failed')
            except BaseException as exc:
                if event in ledger.pending:ledger.unknown(event,type(exc).__name__)
                raise
            finally:
                reset=trainer.restore(initial)
            restored=behavior()
            torch.cuda.synchronize(0)
            require(baseline['teacher_forced_score'].get('valid') is True and
                    after['teacher_forced_score'].get('valid') is True and restored['teacher_forced_score'].get('valid') is True,
                    'missing baseline/update/restored teacher-forcing observation')
            require(trainer.fingerprint()==fingerprint and
                    baseline['generation']['output_token_ids']==restored['generation']['output_token_ids'] and
                    baseline['teacher_forced_score']['nll_sum']==restored['teacher_forced_score']['nll_sum'],
                    'exact reset or deterministic native baseline restoration failed')
            observations.append({'input_tokens':length,'prompt_tokens':row['prompt_tokens'],
                'completion_tokens':row['completion_tokens'],'prepared_sha256':row['prepared_sha256'],
                'before_frozen_base':baseline,'update':update,'after_update':after,'after_restore':restored,
                'reset':reset,'exact_reset':trainer.fingerprint()==fingerprint,
                'baseline_restored_generation_equal':baseline['generation']['output_token_ids']==restored['generation']['output_token_ids'],
                'baseline_restored_nll_equal':baseline['teacher_forced_score']['nll_sum']==restored['teacher_forced_score']['nll_sum'],
                'peak_allocated_bytes':int(torch.cuda.max_memory_allocated(0)),
                'peak_reserved_bytes':int(torch.cuda.max_memory_reserved(0)),
                'elapsed_seconds':time.monotonic()-rung_started,'source':'authored synthetic length-stress identity program'})
            atomic_json(root/('length-'+str(length)+'-observation.json'),observations[-1],exclusive=True)
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)[:512]
    finally:
        elapsed=time.monotonic()-start
        completed=[r['input_tokens'] for r in observations]
        observation={'format':'irisx/qwen14b-capability-child-observation-v1','model_identity':model.identity,
            'status':'measured_ladder' if completed==[128,512,2048] and error is None else 'incomplete_ladder',
            'length_ladder':observations,'completed_lengths':completed,'error':error,'physical_usage':ledger.used,
            'peak_allocated_bytes':max([load_peak]+[r['peak_allocated_bytes'] for r in observations]),
            'measurement_seconds':elapsed,'physical_tokens_per_second':ledger.used['input_tokens']/elapsed,
            'context2048_measured':2048 in completed,'full_context_or_public_coverage_admitted':False,
            'independently_reviewed':False,'automatic_promotion':False,'public_answers_used':False,
            'fp8_executed':False,'tensor_parallel_size':1,'scope':'authored synthetic length ladder; not public solving'}
        atomic_json(root/'child-observation.json',observation,exclusive=True)
        model.close()
    if error is not None:raise RuntimeError(error)


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--child':raise SystemExit('explicit owned launcher required')
    path=Path(sys.argv[2]);require(path.is_file() and path.stat().st_size<=65536,'bounded owned probe request required')
    _child(json.loads(path.read_bytes()))
