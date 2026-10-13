"""Authenticated loader + owned calibration + one-use Session construction.

No production path is reachable in this source-review-only candidate: release.py
requires three externally reviewed pins that deliberately remain unset.
"""
from copy import deepcopy
from pathlib import Path
import os, time
from . import ROOT
from .release import need,verify_inventory,require_production_release
from .admission import _issue,public_receipt,revoke


def _verify_production_native(native,trainer,calibration_sha256):
    import torch
    from tools.arc_qwen_transfer_20261012.decoder import TransferModel,_CALIBRATIONS,_calibration_model_identity
    from tools.arc_qwen_transfer_20261012.backend import TransferTrainer
    from tools.arc_qwen_transfer_20261012.protocol import digest
    from tools.arc_learning_agent_20261011.qwen14b_training import validate_qwen_peft_recipe
    from .storage import storage_plan
    need(type(native) is TransferModel and type(trainer) is TransferTrainer and trainer.native is native,'exact native/trainer owner')
    need(native.tiny_cpu is False and native.identity.get('pretrained_weights_loaded') is True and
         native.identity.get('probe_pretrained_admitted') is True and not native.identity.get('random_test_weights'),'actual authenticated pretrained backend')
    cfg=native.model.config
    need((cfg.hidden_size,cfg.num_hidden_layers,cfg.vocab_size,cfg.num_attention_heads,cfg.num_key_value_heads)==(5120,40,151936,40,8),'exact full14B native topology')
    need((native.context_limit,native.prompt_cap,native.output_cap)==(4096,3072,1024),'exact full-context contract')
    need(torch.cuda.device_count()==1 and all(p.device.type=='cuda' and p.device.index in (None,0) for p in native.model.parameters()),'one actual admitted CUDA device')
    need(sum(p.numel() for p in trainer.parameters.values())==storage_plan()['lora_parameter_count'],'actual production PEFT parameter inventory')
    validate_qwen_peft_recipe(native.model,torch)
    receipt=native._calibration_receipt
    need(receipt is not None and digest(receipt)==calibration_sha256,'actual calibration receipt bound')
    evidence=_CALIBRATIONS.get(calibration_sha256)
    need(evidence is not None and evidence['receipt']==receipt and evidence['native_identity']==_calibration_model_identity(native.identity) and evidence['source_identity']==trainer._source_identity(),'owned calibration registry identity')
    need(receipt['completed_lengths']==[128,512,2048,4096] and receipt['full_context_measured'] is True and receipt['full_state_restoration_verified'] is True,'actual128/512/2048/4096 restored calibration')
    native.assert_decoder_policy()
    need(native.decoder_policy is not None and native.decoder_policy['calibration_sha256']==calibration_sha256,'actual calibrated locked decoder policy')


def _legacy_meter(path, durable):
    """Both ledgers retain unknown reservations; no old-validator compatibility claim."""
    from tools.arc_learning_agent_20261011.budget import WorkLedger
    class CalibrationLedger(WorkLedger):
        def __init__(self):
            super().__init__(path);self.owned_events={}
        def reserve(self,event_id,estimates):
            super().reserve(event_id,estimates)
            phase='calibration-generation' if 'generation' in event_id else 'calibration-operation'
            e=durable.begin_event(phase,durable.global_deadline)
            e.update(legacy_event_id=event_id,reserved_cost=dict(estimates))
            self.owned_events[event_id]=e
            # Reserve is the last metered call before baseline invokes native work.
            # A crash between here and that invocation remains conservatively charged.
            e['dispatched']=True
        def complete(self,event_id,actual,*,status='complete'):
            super().complete(event_id,actual,status=status)
            durable.finish_event(self.owned_events[event_id],status='complete' if status=='excluded' else status,
                                 actual_cost=dict(actual),native_status=status)
        def unknown(self,event_id,reason):
            super().unknown(event_id,reason)
            e=self.owned_events[event_id]
            if 'ended' not in e:durable.finish_event(e,status='unknown',error=reason,charged_cost=dict(self.pending[event_id]))
    return CalibrationLedger()


def _construct(request,plan,clock,output,auth_key,external_release=None,owner_request_sha256=None):
    from .ledger import DurablePhysicalLedger
    from .clock import OriginalClock
    need(type(clock) is OriginalClock and clock.fixture is request['fixture'],'owned clock scope')
    clock.check_mapping();need(plan.global_started==clock.origin_monotonic,'plan cannot restart clock')
    sources=dict(plan.sources.files);verify_inventory(sources)
    fixture=request['fixture']
    if not fixture:
        import inspect
        need(inspect.currentframe().f_back.f_code is open_owned_experiment_session.__code__,'production construction requires owned factory entry')
        from .planning import build_plan
        need(plan.sha256==build_plan(clock,fixture=False).sha256,'actual production plan must equal source builder')
        require_production_release(sources,policy_path=request['policy_path'],environment_path=request['environment_path'],external_release=external_release)
        from .bootstrap import consume_external_release
        consume_external_release(external_release,sources=sources,phase='session',request_sha256=owner_request_sha256,plan_sha256=plan.sha256,clock=clock)
        need(plan.output_cap==1024 and vars(plan.shape)==dict(anchor_updates=256,parents=32,group_size=8,dev_cases=16,holdout_cases=32,max_sweeps=4,max_control_updates=8192,batch_parents=8),'production fixed complete shape')
    import torch
    from tools.arc_qwen_transfer_20261012.decoder import TransferModel,run_calibration
    from tools.arc_qwen_transfer_20261012.backend import TransferTrainer,TransferMeteredModel
    from tools.arc_qwen_transfer_20261012.model_profile import MODEL_KEY,PROFILE_ID,MATERIAL_ADDENDUM_SHA256
    from tools.arc_learning_agent_20261011.metering import MeteredTrainer
    from tools.arc_qwen_transfer_20261012.science_profiles import make_policy
    from tools.arc_qwen_transfer_20261012.protocol import digest
    from rl_session.runtime import Session
    errors=[]
    ledger=DurablePhysicalLedger(torch.device('cpu' if fixture else 'cuda:0'),clock.deadline('inner'),errors.append,
                                 Path(output)/'physical-journal.jsonl',auth_key=auth_key,recover=False)
    native=trainer=grant=session=None
    try:
        config=({'model_key':MODEL_KEY,'profile_id':PROFILE_ID,'material_addendum_sha256':MATERIAL_ADDENDUM_SHA256,
                'tiny_cpu':True,'tokenizer_path':str(ROOT/'baseline/materials/qwen14b/hf-overlay'),
                'tiny_hidden_size':8,'seed':17,'precision':'bf16-base-fp32-lora'} if fixture else
                {**request['model'],'tiny_cpu':False,'_owned_probe_deadline':min(clock.deadline(),time.monotonic()+1790),
                 '_owned_probe_supervisor_pid':os.getppid(),'_owned_probe_scope':'qwen14b-capability-only'})
        config.update(do_sample=False,temperature=1.,top_p=1.)
        with ledger.work('native-load',clock.deadline()) as event:
            if request.get('failure_fixture')=='before_load':raise ValueError('explicit fixture failure before native load')
            event.update(reserved_cost={'native_model_loads':1},dispatched=True)
            native=TransferModel.from_config(config)
            trainer=TransferTrainer(native,{'seed':17 if fixture else 1917,'learning_rate':2e-4,
                'gradient_checkpointing':True,'lora_rank':8,'lora_alpha':16,'schedule_steps':0 if fixture else 256,'warmup_steps':0 if fixture else 4,
                'stability_mode':not fixture,'accumulation_target_tokens':1024,'accumulation_max_microbatches':1,'objective_cycle':['grid']})
            event['actual_cost']={'native_model_loads':1}
        if request.get('failure_fixture')=='after_load':raise ValueError('explicit fixture failure after native load')
        calibration_sha=None
        if not fixture:
            legacy=_legacy_meter(Path(output)/'calibration-work.jsonl',ledger)
            metered=TransferMeteredModel(native,legacy);wrapped=MeteredTrainer(trainer,legacy,max_sequence_tokens=4096)
            calibration=run_calibration(metered,wrapped,legacy,Path(output)/'calibration',clock.deadline())
            need(not legacy.pending,'owned calibration has unresolved physical work')
            need(trainer.optimizer is None and trainer.scheduler is None and not trainer._training_snapshots and not trainer._snapshots and
                 trainer.fingerprint()==trainer._clean_preflight_fingerprint,'actual preflight full-state restoration')
            policy=make_policy(calibration,{'cpu_fixture_only':False,'source_bound_rl_session':True})
            native.lock_decoder_policy(policy)
            trainer.config['decoder_policy_sha256']=native._decoder_policy_sha256
            trainer._base_identity=trainer._model_identity()
            calibration_sha=digest(calibration)
        grant=_issue(native,trainer,ledger,clock,sources,plan.sha256,calibration_sha,fixture=fixture,owner_request_sha256=owner_request_sha256)
        session=Session(native,trainer,global_deadline=clock.deadline(),fixture=fixture,_owned_grant=grant)
        admission=public_receipt(grant)
        admission.update(_actual_native_receipt(session))
        if not fixture:
            import json
            path=Path(request['environment_path'])
            need(path.stat().st_size<=16*1024**2,'bounded reviewed environment artifact')
            expected=json.loads(path.read_text())
            from .environment_v2 import verify_environment
            with ledger.work('environment-admission',clock.deadline()) as event:
                event.update(reserved_cost={'environment_verifications':1},dispatched=True)
                admission['environment_verification']=verify_environment(expected,admission['actual_environment'],
                    model_config=request['model'],native_identity=admission['native_identity'],deadline=clock.deadline())
                event['actual_cost']={'environment_verifications':1}
        return session,admission,ledger
    except BaseException as error:
        if session is not None:
            try:
                closure=session.close()
                error.admission_closure={**closure,'admission_failed':True}
            except BaseException as cleanup_error:
                error.admission_closure={'closed':False,'future_operations_blocked':True,
                    'model_references_released':False,'model_stopped':False,'ledger_settled':False,
                    'admission_failed':True,'cleanup_error':str(cleanup_error)}
            if grant is not None:revoke(grant)
            error.owned_ledger=ledger
            _clear_failure_frames(error)
            raise
        if grant is not None:revoke(grant)
        # The caller receives the durable ledger via an exception attribute and
        # must preserve failed admission evidence even before Session existed.
        cleanup=ledger.start_cleanup(deadline=clock.deadline())
        synchronized=False
        try:
            ledger.sync();synchronized=True
        except BaseException as exc:errors.append(exc)
        finally:
            if trainer is not None:
                trainer.model=None;trainer.parameters.clear();trainer.optimizer=trainer.scheduler=None
                trainer._snapshots.clear();trainer._training_snapshots.clear()
            if native is not None:native.close()
            ledger.finish_event(cleanup,status='complete' if synchronized else 'unclosed-device-error')
            ledger.closed=True
        _clear_failure_frames(error)
        error.owned_ledger=ledger
        error.admission_closure={'closed':True,'future_operations_blocked':True,'model_references_released':True,
            'device_synchronized':synchronized,'model_stopped':synchronized,'ledger_settled':ledger.summary().get('settled',False),
            'fatal_native_state':str(errors[0]) if errors else None,'physical_events':deepcopy(list(ledger.events)),
            'admission_failed':True}
        raise


def open_owned_experiment_session(request,plan,clock,output,auth_key,*,_external_release=None,_owner_request_sha256=None):
    need(type(request) is dict and type(request.get('fixture')) is bool,'explicit owned request scope')
    need(request.get('failure_fixture') is None or request['fixture'] and request['failure_fixture'] in ('before_load','after_load'),'failure injection confined to CPU fixtures')
    need(not any('evaluator' in key or 'gold' in key for key in request),'evaluator access excluded from model child')
    if not request['fixture']:
        import inspect
        from .worker import main
        need(inspect.currentframe().f_back.f_code is main.__code__,'production factory requires canonical owned worker invocation')
    return _construct(request,plan,clock,output,auth_key,_external_release,_owner_request_sha256)


def _actual_native_receipt(session):
    """Observed owned objects only; evidence never substitutes for a grant."""
    import torch,platform,importlib.metadata
    from tools.arc_qwen_transfer_20261012.protocol import digest
    from rl_session.common import digest as checkpoint_digest
    native=session.native;trainer=session.trainer;cfg=native.model.config
    environment={'python_version':platform.python_version(),'torch_version':str(torch.__version__),
        'cuda_version':torch.version.cuda,'cudnn_version':torch.backends.cudnn.version(),
        'device_count':torch.cuda.device_count(),'devices':[]}
    for name in ('transformers','peft','tokenizers'):
        environment[name+'_version']=importlib.metadata.version(name)
    for index in range(environment['device_count']):
        device=torch.cuda.get_device_properties(index)
        environment['devices'].append({'index':index,'name':device.name,'total_memory_bytes':device.total_memory,
                                      'capability':[device.major,device.minor]})
    return {'native_identity':deepcopy(native.identity),'native_hardware':deepcopy(native.hardware),
        'actual_environment':environment,
        'actual_topology':{**{key:getattr(cfg,key) for key in ('hidden_size','num_hidden_layers','vocab_size','num_attention_heads','num_key_value_heads')},
            'context_limit':native.context_limit,'prompt_cap':native.prompt_cap,'output_cap':native.output_cap},
        'peft_parameters':{name:{'dtype':str(p.dtype),'shape':list(p.shape),'elements':p.numel(),'device':str(p.device)}
                           for name,p in trainer.parameters.items()},
        'trainer_base_identity_sha256':digest(native.identity),'trainer_structure_sha256':digest(session._structural),
        'structural_projection':deepcopy(session._structural),
        'canonicalization':{'admission':'json-sort-keys-compact-allow_nan_false-utf8-ascii-escaped-final-newline',
                            'checkpoint':'json-sort-keys-compact-allow_nan_false-utf8-ascii-escaped-no-newline'},
        'checkpoint_base_identity_sha256':checkpoint_digest(native.identity),
        'checkpoint_structure_sha256':checkpoint_digest(session._structural),
        'structural_projection_scope':'same-run-only; process-local callable IDs are not portable'}


def _clear_failure_frames(error):
    # A failed constructor can retain a partially built Session/native tensor
    # through traceback locals even after native/trainer ownership is cleared.
    import traceback
    seen=set();pending=[error]
    while pending:
        current=pending.pop()
        if id(current) in seen:continue
        seen.add(id(current));traceback.clear_frames(current.__traceback__)
        pending.extend(e for e in (current.__cause__,current.__context__) if e is not None)
