"""Build a distinct worker from frozen008 preparation/training definitions.

No historical file is edited. New inference, diagnostics and exception-safe
reset live in this versioned derived worker and its separate source adapter.
"""

FORMAT = 'irisx/nvarc-native-trained-solve-v1'

TAIL = r'''
    from nvarc_native_solve_runtime import (load_sources, SourceModel, cache_controls,
        reset_control, solve_visible, validate_visible)
    import os
    require(os.environ.get('PYTHONHASHSEED')=='0','frozen source verification hash seed required')
    visible=json.loads((output.parent/'visible.json').read_bytes())
    validate_visible(visible)
    require(digest(visible)==plan['visible_digest'],'exact visible task binding differs')
    loader,solver,decoder=load_sources(output.parent,torch,np)
    def emit(event,**details):
        record={'event':event,'elapsed_seconds':time.monotonic()-started,**details}
        with (output/'solve-events.jsonl').open('ab') as stream:
            stream.write((json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())
            stream.flush()
    adapter=SourceModel(model,torch,emit,forward_limits=plan['inference_forward_limits'],
        input_token_limit=plan['maximum_inference_input_tokens'],generation_deadline=0)
    budget=None;control=None;solve=None;trained=None;moments=None;post_reset=None
    training_complete=False;failures=[];pending_error=None;reset_verified=False;task_started=None;elapsed=None
    def release_optimizer():
        if budget is not None and budget.optimizer is not None:
            budget.optimizer.zero_grad(set_to_none=True)
            budget.optimizer.state.clear()
            require(not budget.optimizer.state,'all optimizer tensor state must be discarded')
            budget.optimizer=None
        trainer.optimizer=None;trainer.lr_scheduler=None
        trainer.accelerator._optimizers.clear();trainer.accelerator._schedulers.clear()
    try:
        FastLanguageModel.for_inference(model)
        control=cache_controls(adapter)
        save('cache-control.json',control)
        FastLanguageModel.for_training(model)
        current_flags=[{'module':name,'value':module.gradient_checkpointing} for name,module in model.named_modules()
            if hasattr(module,'gradient_checkpointing')]
        require(current_flags==flags,'native training checkpoint flags changed after cache controls')
        require(tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch)==baseline,
            'cache controls changed trainable tensor bytes before training')
        budget=EpochBudget(torch,model,trainer,rows,rates,lambda value:save('training-ledger.json',value),
            expected_parameters=PARAMETERS,expected_dtype='torch.bfloat16')
        training_start=time.monotonic();task_started=time.time()
        with budget.installed():
            trainer.train()
            moments=budget.complete()
        torch.cuda.synchronize();elapsed=time.monotonic()-training_start
        require(trainer.state.global_step==128 and trainer.state.epoch==1,'complete native epoch required')
        trained=tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch)
        require(trained!=baseline,'native epoch must change saved tensors')
        save('trained-inventory.json',trained);save('optimizer-state.json',moments)
        training_complete=True
        release_optimizer()
        require(trainer.accelerator.unwrap_model(model,keep_fp32_wrapper=False) is model,
            'unexpected wrapped native model; do not change the observed adapter identity')
        FastLanguageModel.for_inference(model)
        import gc
        gc.collect();torch.cuda.empty_cache()
        adapter.generation_deadline=min(time.time()+plan['maximum_inference_seconds'],
            task_started+plan['diagnostic_task_seconds'],
            time.time()+plan['maximum_child_wall_seconds']-120-(time.monotonic()-started))
        with torch.inference_mode():
            solve=solve_visible(visible,loader,solver,decoder,tokenizer,adapter,
                task_started=task_started,task_seconds=plan['diagnostic_task_seconds'],
                maximum_candidates=plan['maximum_candidate_sequences'],emit=emit)
        save('solve-result.json',solve)
    except BaseException as error:
        pending_error=error
        failures.append({'phase':'pipeline','error_type':type(error).__name__,'error_message':str(error)[:1200]})
    finally:
        # Cleanup, restoration and post-reset control are independent attempts.
        # Abrupt process termination can prevent finalization; never infer reset.
        try:
            release_optimizer()
        except BaseException as error:
            if pending_error is None:pending_error=error
            failures.append({'phase':'optimizer_cleanup','error_type':type(error).__name__,'error_message':str(error)[:1200]})
        try:
            set_peft_model_state_dict(model,defaults.copy(),adapter_name='default')
            restored=tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch)
            require(restored==baseline,'all original saved tensors must reset exactly')
            save('reset-inventory.json',restored);reset_verified=True
        except BaseException as error:
            if pending_error is None:pending_error=error
            failures.append({'phase':'adapter_restoration','error_type':type(error).__name__,'error_message':str(error)[:1200]})
        if reset_verified and control is not None:
            try:
                FastLanguageModel.for_inference(model)
                post_reset=reset_control(adapter,control)
                save('post-reset-control.json',post_reset)
            except BaseException as error:
                post_reset=None
                if pending_error is None:pending_error=error
                failures.append({'phase':'post_reset_control','error_type':type(error).__name__,'error_message':str(error)[:1200]})
        optimizer_discarded=(trainer.optimizer is None and trainer.lr_scheduler is None
            and not trainer.accelerator._optimizers and not trainer.accelerator._schedulers
            and (budget is None or budget.optimizer is None))
        if failures:
            save('pipeline-failure.json',{'failures':failures})
        result={'run_id':plan['run_id'],'plan_digest':digest(plan),
            'outcome':'failed' if failures else 'complete' if solve is not None and solve['outcome']=='complete'
                and reset_verified and post_reset is not None and optimizer_discarded else 'inconclusive',
            'failures':failures,
            'training_complete':training_complete,'all_saved_tensors_restored':reset_verified,
            'post_reset_control_verified':post_reset is not None,'optimizer_discarded':optimizer_discarded,
            'training_wall_seconds':elapsed,'worker_wall_seconds':time.monotonic()-started,
            'training_forwards':0 if budget is None else sum(r['completed'] for r in budget.state['forwards']),
            'optimizer_steps':0 if budget is None else sum(r['completed'] for r in budget.state['optimizer_steps']),
            'training_input_tokens':0 if budget is None else sum(r['input_tokens'] for r in budget.state['forwards']),
            'inference_forwards_reserved':adapter.reserved,'inference_forwards_completed':adapter.completed,
            'inference_physical_input_tokens':adapter.input_tokens,
            'inference_input_tokens_by_phase':adapter.input_by_phase,
            'solve':solve,'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'cuda_peak_reserved_bytes':torch.cuda.max_memory_reserved(),
            'contains_evaluator_truth':False,'correctness_scored':False,'checkpoint_exported':False,
            'teacher_calls':0,'paid_usd':0,'full_numerical_parity_claim':False,
            'scope':'one source-exposed development task; native trained generation/ranking/reset control, not ARC quality'}
        save('pipeline-result.json',result)
    if pending_error is not None:
        raise pending_error
'''


def worker(source):
    old = "FORMAT='irisx/nvarc-original-native-long-ttt-v2'"
    anchor = '    budget=EpochBudget('
    main = "\n\nif __name__=='__main__':"
    if source.count(old) != 1 or source.count(anchor) != 1 or source.count(main) != 1:
        raise RuntimeError('frozen008 portable worker anchors differ')
    guard_start = source.index("    require(plan['format']==FORMAT")
    guard_end = source.index("    parent=json.loads", guard_start)
    guard = """    require(plan['format']==FORMAT and plan['approved'] is True and
        plan['control_version']=='1.2.0' and plan['maximum_training_forwards']==plan['maximum_optimizer_steps']==128 and
        plan['maximum_generations']==4 and plan['maximum_teacher_calls']==plan['maximum_paid_usd']==0,
        'admitted finite native trained-solve envelope required')
"""
    source = source[:guard_start] + guard + source[guard_end:]
    source = source.replace(old, "FORMAT=" + repr(FORMAT))
    prefix = source.split(anchor, 1)[0]
    suffix = main + source.split(main, 1)[1]
    result = prefix + TAIL + suffix
    compile(result, 'native-trained-solve-worker', 'exec')
    return result.encode('utf-8')


COUNTERS = '''def inference_counts():
    events=[];path=work/'native/solve-events.jsonl';truncated=False
    if path.is_file():
        for line in path.read_bytes().splitlines():
            try:events.append(json.loads(line))
            except (ValueError,UnicodeDecodeError):truncated=True;break
    reserved=[e for e in events if e.get('event')=='forward_reserved']
    completed=[e for e in events if e.get('event')=='forward_completed']
    return {'reserved':len(reserved),'completed':len(completed),
        'generations':sum(e.get('event')=='generation_reserved' for e in events),
        'ledger_truncated':truncated}

def counts():
    path=work/'native/training-ledger.json'
    state=json.loads(path.read_bytes()) if path.is_file() else {'forwards':[],'optimizer_steps':[],'training_steps':[]}
    inference=inference_counts();training=sum(r['completed'] for r in state['forwards'])
    return {'model_forwards':training+inference['completed'],
        'training_model_forwards':training,'inference_model_forwards':inference['completed'],
        'optimizer_steps':sum(r['completed'] for r in state['optimizer_steps']),
        'model_forwards_reserved':len(state['forwards'])+inference['reserved'],
        'optimizer_steps_reserved':len(state['optimizer_steps']),
        'training_steps_reserved':len(state['training_steps']),
        'inference_ledger_truncated':inference['ledger_truncated']}

'''


def parent(source):
    begin, end = source.index('def counts():'), source.index('def save(name,value):')
    source = source[:begin] + COUNTERS + source[end:]
    anchor = "('nvarc_native_ttt_schedule.py','schedule')"
    if source.count(anchor) != 1 or source.count("'generations':0") != 2:
        raise RuntimeError('frozen008 parent file/cost anchors differ')
    source = source.replace(anchor, anchor + ",('arc_loader.py','loader'),('arc_decoder.py','decoder'),"
        "('nvarc_native_solve_runtime.py','solve_runtime'),('visible.json','visible')")
    source = source.replace("'generations':0", "'generations':inference_counts()['generations']")
    source = source.replace("phase='complete-native-source-epoch'", "phase='native-trained-solve'")
    source = source.replace("TOKENIZERS_PARALLELISM='false'", "TOKENIZERS_PARALLELISM='false',PYTHONHASHSEED='0'")
    anchor = "save('plan.json',plan);save('payload-bindings.json',HASHES)"
    if source.count(anchor) != 1:
        raise RuntimeError('native parent admission anchor differs')
    source = source.replace(anchor, anchor + "\n    if plan['approved'] is not True or not plan.get('controller_admission_sha256'):\n"
        "        raise RuntimeError('inert package: controller resource admission required before runtime')")
    compile(source, 'native-trained-solve-parent', 'exec')
    return source
