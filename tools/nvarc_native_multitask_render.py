"""New worker/parent bytes derived from retained native008 preparation."""
from tools.nvarc_native_multitask import FORMAT

TAIL = r'''
    from tools.nvarc_native_multitask import (Events, EvidenceModel, solve_test,
        run_task_tests, training_deadline, write, digest as value_digest)
    from tools.nvarc_native_submission import task_binding
    from tools.nvarc_native_solve_runtime import (load_sources,cache_controls,reset_control,discard_optimizer_state)
    import os
    require(os.environ.get('PYTHONHASHSEED')=='0','original verifier hash seed required')
    challenges=json.loads((root/'challenges.json').read_bytes())
    binding=task_binding(plan,challenges,task_id)
    binding['attempt_id']=attempt_id
    events=Events(output/'events.jsonl',binding)
    loader,solver,decoder=load_sources(root,torch,np)
    limits=spec['inference_forward_limits']
    adapter=EvidenceModel(model,torch,events.emit,forward_limits=limits,
        input_token_limit=spec['maximum_inference_input_tokens'],generation_deadline=0,
        per_test_limits=spec['per_test_limits'])
    budget=None;control=None;post_reset=None;failures=[];training_complete=False
    reset_verified=False;tests=[];elapsed=None;moments=None
    task_started=time.time();task_deadline=min(task_started+spec['task_seconds'],
        float(os.environ['IRIS_NATIVE_CHILD_DEADLINE'])-spec['reset_reserve_seconds'])
    def checkpoint(values):
        write(output/'checkpoint.json',{'binding':binding,'tests':values,
            'event_count':events.sequence,'event_head':events.head})
    def release():
        discard_optimizer_state(model,trainer,budget)
    try:
        FastLanguageModel.for_inference(model)
        control=cache_controls(adapter);save('cache-control.json',control)
        require(tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch)==baseline,
            'cache controls changed baseline tensors')
        if mode!='baseline-only':
            FastLanguageModel.for_training(model)
            require([{'module':name,'value':module.gradient_checkpointing} for name,module in model.named_modules()
                if hasattr(module,'gradient_checkpointing')]==flags,'native checkpoint flags changed')
            budget=EpochBudget(torch,model,trainer,rows,rates,lambda v:save('training-ledger.json',v),
                expected_parameters=PARAMETERS,expected_dtype='torch.bfloat16')
            if mode=='fault-after-two-updates':
                original_step=trainer.training_step
                def injected(*a,**kw):
                    if len(budget.state['optimizer_steps'])>=2:
                        raise RuntimeError('planned isolation fault after two native updates')
                    return original_step(*a,**kw)
                trainer.training_step=injected
            start_training=time.monotonic()
            with training_deadline(budget,task_deadline-spec['inference_reserve_seconds']):
                trainer.train();moments=budget.complete()
            torch.cuda.synchronize();elapsed=time.monotonic()-start_training
            require(trainer.state.global_step==len(rows) and trainer.state.epoch==1,'full derived native epoch required')
            trained=tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch)
            require(trained!=baseline,'native epoch did not change tensors')
            save('trained-inventory.json',trained);save('optimizer-state.json',moments);training_complete=True
            release()
            require(trainer.accelerator.unwrap_model(model,keep_fp32_wrapper=False) is model,'native model identity differs')
            FastLanguageModel.for_inference(model)
            import gc
            gc.collect();torch.cuda.empty_cache()
            adapter.generation_deadline=min(task_deadline,time.time()+spec['inference_seconds'])
            with torch.inference_mode():
                tests,failure=run_task_tests(challenges,task_id,lambda index:solve_test(challenges,task_id,index,
                    loader,solver,decoder,tokenizer,adapter,maximum_candidates=spec['maximum_candidate_sequences_per_test'],
                    emit=events.emit),checkpoint)
            if failure:failures.append({'phase':'solve',**failure})
    except BaseException as error:
        failures.append({'phase':'pipeline','error_type':type(error).__name__,'error_message':str(error)[:1200]})
    finally:
        # Parent SIGKILL/OOM cannot reach this path and cannot claim reset.
        try:
            save('pre-reset-inventory.json',tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch))
        except BaseException as error:failures.append({'phase':'pre-reset-inventory','error_type':type(error).__name__,'error_message':str(error)[:1200]})
        try:release()
        except BaseException as error:failures.append({'phase':'cleanup','error_type':type(error).__name__,'error_message':str(error)[:1200]})
        try:
            set_peft_model_state_dict(model,defaults.copy(),adapter_name='default')
            reset=tensor_inventory(get_peft_model_state_dict(model,adapter_name='default'),torch)
            require(reset==baseline,'native adapter restoration differs');save('reset-inventory.json',reset);reset_verified=True
        except BaseException as error:failures.append({'phase':'reset','error_type':type(error).__name__,'error_message':str(error)[:1200]})
        if reset_verified and control is not None:
            try:
                FastLanguageModel.for_inference(model);post_reset=reset_control(adapter,control);save('post-reset-control.json',post_reset)
            except BaseException as error:failures.append({'phase':'reset-control','error_type':type(error).__name__,'error_message':str(error)[:1200]})
        discarded=(trainer.optimizer is None and trainer.lr_scheduler is None and
            not trainer.accelerator._optimizers and not trainer.accelerator._schedulers and
            (budget is None or budget.optimizer is None) and all(p.grad is None for p in model.parameters()))
        outcome=('failed' if failures else 'complete' if reset_verified and post_reset is not None and discarded and
            (mode=='baseline-only' or training_complete and len(tests)==len(challenges[task_id]['test']) and
             all(t.get('native_complete') for t in tests)) else 'inconclusive')
        result={'binding':binding,'mode':mode,'outcome':outcome,'failures':failures,
            'training_complete':training_complete,'all_saved_tensors_restored':reset_verified,
            'post_reset_control_verified':post_reset is not None,'optimizer_discarded':discarded,
            'worker_wall_seconds':time.monotonic()-started,'training_wall_seconds':elapsed,
            'inference_forwards_reserved':adapter.reserved,'inference_forwards_completed':adapter.completed,
            'inference_input_tokens_by_phase':adapter.input_by_phase,'tests':tests,
            'contains_evaluator_truth':False,'correctness_scored':False,'teacher_calls':0,'paid_usd':0}
        save('result.json',result)
    if failures:raise RuntimeError('native worker failed; retained exact failure and prior checkpoints')
'''


def worker(old_worker):
    source=old_worker.decode()
    anchor='    from nvarc_native_ttt_schedule import native_schedule'
    prefix=source.split(anchor)[0]
    start=prefix.index("    require(plan['format']==FORMAT")
    end=prefix.index('    parent=json.loads',start)
    prefix=prefix[:start]+'''    require(plan['format']==FORMAT and plan['approved'] is True and
        plan['controller_admission'] is not None and plan['maximum_paid_usd']==plan['maximum_teacher_calls']==0,
        'separately admitted finite native multi-task plan required')
    root=output.parents[2];attempt_id=output.parent.name
    attempt=next(a for a in plan['worker_attempts'] if a['attempt_id']==attempt_id)
    task_id=attempt['task_id'];mode=attempt['mode'];spec=plan['task_specs'][task_id]
    require(len(rows)==spec['training_forwards'] and digest(rows)==spec['expected_rows_digest'] and
        digest(texts)==spec['texts_digest'],'exact task-derived public training rows required')
'''+prefix[end:]
    prefix=prefix.replace("FORMAT='irisx/nvarc-original-native-long-ttt-v2'",'FORMAT='+repr(FORMAT))
    prefix=prefix.replace("FORMAT='irisx/nvarc-native-trained-solve-v1'",'FORMAT='+repr(FORMAT))
    prefix=prefix.replace("output.parent/'parent-verification.json'","root/'parent-verification.json'")
    prefix=prefix.replace("output.parent/'hardware.json'","root/'hardware.json'")
    prefix=prefix.replace("plan['source_learning_rates']","spec['source_learning_rates']")
    suffix=source[source.index("\n\nif __name__=='__main__':"):]
    schedule="    from nvarc_native_ttt_schedule import native_schedule\n    rates,schedule=native_schedule(dependency,trainer.args,spec['source_learning_rates'])\n    save('native-schedule.json',schedule)\n"
    result=prefix+schedule+TAIL+suffix
    compile(result,'native-multitask-worker','exec')
    return result.encode()


LOOP = r'''
    for name,key in FILES.items():
        path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw[key])
    (work/'tools/__init__.py').write_bytes(b'')
    sys.path.insert(0,str(work))
    from tools.nvarc_native_multitask import write as retain, digest as value_digest
    from tools.nvarc_native_submission import build_native_submission, read_task_evidence
    phase='sequential-native-tasks'
    receipts=[]
    for attempt in plan['worker_attempts']:
        task_id=attempt['task_id'];attempt_id=attempt['attempt_id']
        directory=work/'tasks'/attempt_id;directory.mkdir(parents=True)
        receipt={'task_id':task_id,'attempt_id':attempt_id,'status':'not_executed','launched':False,
            'returncode':None,'reset_inferred':False}
        receipts.append(receipt);save('worker-receipts.json',receipts)
        remaining=min(plan['maximum_child_wall_seconds'],plan['maximum_notebook_wall_seconds']-
            plan['packaging_reserve_seconds']-(time.monotonic()-START))
        if remaining<plan['minimum_worker_admission_seconds']:
            receipt['status']='session_limit';save('worker-receipts.json',receipts);continue
        material=json.loads(gzip.decompress(raw['task_materials_gzip']))[task_id]
        retain(directory/'texts.json',material['texts']);retain(directory/'expected-rows.json',material['rows'])
        environment=dict(os.environ,PYTHONPATH=str(work)+os.pathsep+str(dependency),CUDA_VISIBLE_DEVICES='0',
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',UNSLOTH_DISABLE_STATISTICS='1',
            WANDB_DISABLED='true',TOKENIZERS_PARALLELISM='false',PYTHONIOENCODING='utf-8',PYTHONHASHSEED='0',
            TRITON_PTXAS_PATH='/usr/local/cuda/bin/ptxas',OMP_NUM_THREADS='2',
            IRIS_NATIVE_CHILD_DEADLINE=str(time.time()+remaining))
        command=[sys.executable,str(work/'inspection.py'),'--plan',str(work/'plan.json'),'--model',str(model),
            '--dependency',str(dependency),'--solver',str(work/'solver.py'),'--texts',str(directory/'texts.json'),
            '--rows',str(directory/'expected-rows.json'),'--output',str(directory/'native')]
        # Save dispatch reservation before Popen, including a failed Popen.
        receipt.update(status='interrupted_pending',launched=True,reserved_seconds=remaining)
        save('worker-receipts.json',receipts)
        with (directory/'stdout.log').open('w',encoding='utf-8') as stdout,(directory/'stderr.log').open('w',encoding='utf-8') as stderr:
            process=None
            try:
                process=subprocess.Popen(command,env=environment,stdout=stdout,stderr=stderr,start_new_session=True)
                code=process.wait(timeout=remaining)
                receipt.update(returncode=code,status='complete' if code==0 else 'worker_crash')
            except BaseException as error:
                if process is not None and process.poll() is None:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait(timeout=10)
                receipt.update(status='timeout' if isinstance(error,subprocess.TimeoutExpired) else 'interrupted_pending',
                    error_type=type(error).__name__,error_message=str(error)[:1000])
                save('worker-receipts.json',receipts)
                if not isinstance(error,Exception):raise
        path=directory/'native/result.json'
        if path.is_file() and receipt['status']=='worker_crash':
            result=json.loads(path.read_bytes())
            receipt['status']='oom' if any('out of memory' in r['error_message'].lower() for r in result['failures']) else 'failed'
        save('worker-receipts.json',receipts)
    phase='verified-native-submission-export'
    final_export()
    phase='terminal'
    save('terminal.json',{'run_id':RUN,'outcome':'complete' if all(r['status']=='complete' for r in receipts) else 'failed',
        'phase':phase,'contains_evaluator_truth':False,'correctness_scored':False,'teacher_calls':0,'paid_usd':0,
        'wall_seconds':time.monotonic()-START,'worker_receipts_digest':value_digest(receipts)})
'''


PARENT_HELPERS = r'''
def counts():
    result={'model_forwards':0,'optimizer_steps':0,'model_forwards_reserved':0,'optimizer_steps_reserved':0,
        'training_steps_reserved':0,'generations':0,'inference_ledger_truncated':False}
    for path in (work/'tasks').glob('*/native/training-ledger.json'):
        state=json.loads(path.read_bytes())
        result['model_forwards']+=sum(r['completed'] for r in state['forwards'])
        result['optimizer_steps']+=sum(r['completed'] for r in state['optimizer_steps'])
        result['model_forwards_reserved']+=len(state['forwards'])
        result['optimizer_steps_reserved']+=len(state['optimizer_steps'])
        result['training_steps_reserved']+=len(state['training_steps'])
    for path in (work/'tasks').glob('*/native/events.jsonl'):
        for line in path.read_bytes().splitlines(keepends=True):
            if not line.endswith(b'\n'):
                result['inference_ledger_truncated']=True;break
            row=json.loads(line);kind=row['event']
            result['model_forwards']+=kind=='forward_completed'
            result['model_forwards_reserved']+=kind=='forward_reserved'
            result['generations']+=kind=='generation_reserved'
    return result

def final_export():
    from tools.nvarc_native_multitask import write as retain
    from tools.nvarc_native_submission import read_task_evidence,build_native_submission
    from tokenizers import Tokenizer
    tok=Tokenizer.from_file(str(model/'tokenizer.json'))
    class Tokens:
        def encode(self,text):return tok.encode(text).ids
        def decode(self,values):return tok.decode(values,skip_special_tokens=False)
    challenges=json.loads(raw['challenges'])
    receipts=json.loads((work/'worker-receipts.json').read_bytes())
    evidence=read_task_evidence(work,plan,challenges,receipts)
    submission,audit=build_native_submission(challenges,plan,evidence,work,Tokens())
    retain(work/'native-evidence.json',evidence);retain(work/'submission-audit.json',audit);retain(work/'submission.json',submission)
'''


ISOLATED_EXPORT = r'''
def final_export():
    remaining=plan['maximum_notebook_wall_seconds']-(time.monotonic()-START)
    limit=min(plan['maximum_export_process_seconds'],remaining)
    if limit<=0:raise RuntimeError('native CPU export deadline exhausted')
    environment=dict(os.environ,PYTHONHASHSEED='0',CUDA_VISIBLE_DEVICES='',
        PYTHONPATH=str(work)+os.pathsep+str(dependency),HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',PYTHONIOENCODING='utf-8',OMP_NUM_THREADS='2')
    command=[sys.executable,str(work/'tools/nvarc_native_export.py'),'--root',str(work),
        '--tokenizer',str(model/'tokenizer.json')]
    with (work/'export.stdout.log').open('ab') as stdout,(work/'export.stderr.log').open('ab') as stderr:
        subprocess.run(command,env=environment,stdout=stdout,stderr=stderr,timeout=limit,check=True)
'''


def parent(source, files, archive_source, *, isolated_export=False):
    # Reuse exact native source/model/hardware verification, replace the whole
    # single-worker dispatch and both terminal paths, never historic bytes.
    start_counts=source.index('def counts():');end_counts=source.index('def save(name,value):',start_counts)
    helpers=PARENT_HELPERS
    if isolated_export:
        helpers=helpers[:helpers.index('\ndef final_export():')]+ISOLATED_EXPORT
    source=source[:start_counts]+helpers+'\n'+source[end_counts:]
    source=source.replace("save('plan.json',plan);save('payload-bindings.json',HASHES)",
        "save('plan.json',plan);save('payload-bindings.json',HASHES)\n    if plan['approved'] is not True or plan['controller_admission'] is None:\n        raise RuntimeError('inert package: new owner-Editor resource admission required')")
    source=source.replace("    phase='original-source-inventory'", "    import shutil\n    if shutil.disk_usage(work).free < plan['minimum_free_working_bytes']:\n        raise RuntimeError('native multi-task working-space reserve unavailable')\n    phase='original-source-inventory'")
    start=source.index("    text_bytes=gzip.decompress(raw['texts_gzip'])")
    end=source.index('\nexcept BaseException as error:',start)
    source=source[:start]+LOOP+source[end:]
    begin=source.index('\nfinally:\n')
    source=source[:begin]+r'''
finally:
    if plan is not None:
        # After a parent interrupt/worker crash, recompute from only durable
        # test checkpoints. Preserve the failed terminal; never infer reset.
        if (work/'worker-receipts.json').is_file() and not (work/'submission.json').is_file():
            try:final_export()
            except BaseException as error:
                terminal=json.loads((work/'terminal.json').read_bytes())
                terminal.update(outcome='failed',export_failure={'error_type':type(error).__name__,'error_message':str(error)[:1000]})
                save('terminal.json',terminal)
        terminal=json.loads((work/'terminal.json').read_bytes());terminal.update(counts());save('terminal.json',terminal)
        destination=write_editor_archive(work,work.parent/'結果.zip',RUN,plan)
        show_editor_archive(destination,RUN,'sha256:'+hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest())
'''
    source=archive_source+'\nFILES='+repr(files)+'\n'+source
    source=source.replace('>16*1024**2','>96*1024**2')
    compile(source,'native-multitask-parent','exec')
    return source
