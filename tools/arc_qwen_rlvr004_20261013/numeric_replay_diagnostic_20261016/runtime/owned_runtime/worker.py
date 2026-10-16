"""Single owned model process. PUBLIC evaluator path/answers never enter it."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'baseline'),str(ROOT/'baseline/src')]
sys.dont_write_bytecode=True
from owned_runtime.release import closed_bootstrap,need,verify_inventory,file_sha,canonical
closed_bootstrap()
import json,os,time


def _finalize_physical_events(ledger,model_closure,root):
    """Emit the same durable event union even when factory admission failed.

    Closure flags and failures are preserved. An unsettled/damaged ledger must
    never be converted into a successful model closure by this projection.
    """
    from experiment_flow.contracts import write_json
    from experiment_flow.metering import compact_event_projections
    need(type(model_closure) is dict,'model closure required for physical projection')
    summary=ledger.summary()
    need(summary['closed'] and summary['integrity_ok'],'authenticated closed journal required for physical projection')
    events=summary['physical_events']
    need(events==list(ledger.events),'durable journal/event union differs before final projection')
    reference=model_closure.get('physical_events_ref')
    if reference is None:
        need(model_closure.get('physical_events')==events,'failed-admission closure/event union differs')
        reference=write_json(Path(root)/'physical-events.json',events)
        model_closure=compact_event_projections(model_closure,reference)
    else:
        path=Path(reference['path'])
        need(path.resolve().is_relative_to(Path(root).resolve()) and not path.is_symlink() and
             file_sha(path)==reference['file_sha256'] and json.loads(path.read_bytes())==events,
             'existing final physical event stream differs from durable journal')
    ledger.seal_artifact(reference['path'],label='physical-events')
    return model_closure


def main():
    need(len(sys.argv)==4,'owned request file, exact hash and private key descriptor required')
    request_path=Path(sys.argv[1]);expected=sys.argv[2];fd=int(sys.argv[3])
    need(request_path.is_file() and not request_path.is_symlink() and request_path.stat().st_size<1024**2,'bounded regular owned request')
    need(file_sha(request_path)==expected,'owner request byte identity differs')
    request=json.loads(request_path.read_text());key=os.read(fd,33);os.close(fd)
    need(len(key)==32,'one parent-owned authentication key')
    need(request['format']=='owned-rl-worker-request-v1','owned request schema')
    verify_inventory(request['sources'])
    from owned_runtime.clock import OriginalClock
    clock=OriginalClock.from_receipt(request['clock']);config=request['config'];root=Path(request['output_root'])
    if not config['fixture']:
        from owned_runtime.parent_scoring import verify_child_loader_environment
        verify_child_loader_environment(request,deadline=clock.deadline())
    from owned_runtime.planning import build_plan
    from owned_runtime.factory import open_owned_experiment_session
    from owned_runtime.backend import NativeOwnedAdapter,OwnedDataset,OwnedRewardPanel
    from experiment_flow.native import AuthenticatedBaselineDataset,NativeTinyRewardPanel
    from experiment_flow.contracts import write_json,SourceExecutionGuard
    from experiment_flow.flow import (run_training_numeric_diagnostic, NUMERIC_DIAGNOSTIC_PURPOSE,
                                      NUMERIC_DIAGNOSTIC_COMPLETE)
    need(request.get('run_purpose')==NUMERIC_DIAGNOSTIC_PURPOSE,'fixed training-only diagnostic request required')
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    from owned_runtime.evidence import register_output
    register_output(root)
    plan=build_plan(clock,fixture=config['fixture'])
    need(plan.sha256==request['plan_sha256'],'owner/child plan binding differs')
    guard=SourceExecutionGuard(plan.sources)
    external_release=None
    if not config['fixture']:
        from owned_runtime.bootstrap import reverify_child_release
        external_release=reverify_child_release(request_path,expected,request=request,sources=request['sources'],plan_sha256=plan.sha256,clock=clock)
    session=ledger=adapter=None;result=None;error=None;model_closure=None
    try:
        need(time.monotonic()<clock.deadline(),'original inner clock expired before load')
        if config['fixture']:
            dataset=AuthenticatedBaselineDataset.build_tiny(root/'authenticated-fixture-data',dev_cases=2,holdout_cases=2)
            panel=NativeTinyRewardPanel(dataset)
        else:
            from owned_runtime.parent_scoring import preflight_child_driver
            write_json(root/'child-driver-resolution.json',preflight_child_driver(deadline=clock.deadline()))
            dataset=OwnedDataset.build({'tiny_cpu':False,'training_root':config['training_root']},root/'dataset')
            panel=OwnedRewardPanel(dataset,config['training_root'])
        session,admission,ledger=open_owned_experiment_session(config,plan,clock,root,key,_external_release=external_release,_owner_request_sha256=expected)
        write_json(root/'session-admission.json',admission)
        adapter=NativeOwnedAdapter(session)
        result=run_training_numeric_diagnostic(adapter,dataset,panel,plan,root/'experiment')
        model_closure=result['model_closure']
        need(result['status']==NUMERIC_DIAGNOSTIC_COMPLETE and result.get('diagnostic_complete') is True,
             'training-only numeric diagnostic incomplete: '+str(result.get('error',result.get('diagnostic_stop_reason'))))
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)}
        if getattr(exc,'child_driver_resolution',None) is not None:
            write_json(root/'child-driver-resolution.json',exc.child_driver_resolution)
        ledger=ledger or getattr(exc,'owned_ledger',None)
        model_closure=model_closure or getattr(exc,'admission_closure',None)
    finally:
        if session is not None and not session._closed:
            try:model_closure=session.close()
            except BaseException as exc:model_closure={'closed':False,'error':str(exc)}
        physical_finalization_error=None
        if ledger is not None:
            try:model_closure=_finalize_physical_events(ledger,model_closure,root)
            except BaseException as exc:
                physical_finalization_error={'type':type(exc).__name__,'message':str(exc)}
                error=error or physical_finalization_error
        closure={'format':'owned-rl-inner-closure-v1','status':'complete' if error is None else 'stopped-incomplete',
            'request_sha256':expected,'plan_sha256':plan.sha256,'clock':clock.receipt(),'model_closure':model_closure,
            'error':error,'physical_finalization_error':physical_finalization_error,'public_gold_opened':False,'scope':'source-review-only-unpublishable',
            'result_ref':None if result is None else {'path':result['result_artifact'],'file_sha256':file_sha(result['result_artifact'])}}
        try:closure['source_closure']=plan.sources.close_imports(guard)
        except BaseException as exc:
            closure['source_closure']={'verified':False,'error':str(exc)};closure['status']='stopped-incomplete';error=error or {'type':'SourceClosure','message':str(exc)}
            closure['error']=error
        write_json(root/'inner-closure.json',closure)
        if ledger is not None:ledger.seal_artifact(root/'inner-closure.json')
        guard.stop()
    if error is not None:raise RuntimeError(error['type']+': '+error['message'])

if __name__=='__main__':
    from owned_runtime.worker import main as _main
    _main()
