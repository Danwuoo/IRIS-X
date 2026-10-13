"""Owned source/clock parent runner. Candidate has no production launch authority."""
from pathlib import Path
import argparse,json,os,sys,time,uuid
ROOT=Path(__file__).resolve().parents[1]
if __package__ in (None,''):
    sys.path[:0]=[str(ROOT),str(ROOT/'baseline'),str(ROOT/'baseline/src')]
from owned_runtime.release import need,inventory,source_digest,verify_inventory,require_production_release,check_production_pins,closed_bootstrap,file_sha,canonical,sha
closed_bootstrap()
from owned_runtime.clock import OriginalClock


def run_owned(config,output,*,original_epoch,synthetic_score=False,external_context=None):
    need(type(config) is dict and type(config.get('fixture')) is bool,'explicit source-owned configuration')
    fixture=config['fixture'];raw_root=Path(output).absolute()
    need(all(not p.is_symlink() for p in (raw_root,*raw_root.parents)),'regular output ancestry')
    root=raw_root.resolve()
    need(not root.exists() and not root.is_relative_to(ROOT) and not ROOT.is_relative_to(root),'new nonoverlapping owned output')
    need(all(not p.is_symlink() for p in (root,*root.parents)),'regular output ownership')
    from owned_runtime.parent_scoring import validate_model_config, worker_environment, require_parent_scorer
    validate_model_config(config)
    need(type(synthetic_score) is bool and (not synthetic_score or fixture and external_context is None),
         'legacy synthetic scorer requires a standalone fixture, never production or checked parent assembly')
    sources=inventory()
    if not fixture:
        from owned_runtime.bootstrap import context_receipt
        context_receipt(external_context)
        check_production_pins(sources,policy_path=config['policy_path'],environment_path=config['environment_path'])
        require_parent_scorer(external_context,config=config)
    else:
        need(set(config)<={'fixture','failure_fixture'},'closed tiny CPU fixture configuration')
        if external_context is not None:
            from owned_runtime.bootstrap import context_receipt
            require_parent_scorer(external_context,config=config)
    clock=OriginalClock.create(original_epoch,uuid.uuid4().hex,fixture=fixture)
    from owned_runtime.planning import build_plan
    from experiment_flow.contracts import write_json
    from owned_runtime.supervisor import run_supervised
    from owned_runtime.storage import storage_plan,before_session
    plan=build_plan(clock,fixture=fixture)
    root.mkdir(parents=True,exist_ok=False)
    from owned_runtime.evidence import register_output,expansion_plan
    register_output(root)
    write_json(root/'session-disk-admission.json',before_session(root,fixture=fixture))
    write_json(root/'evidence-expansion-plan.json',expansion_plan())
    write_json(root/'owner-clock.json',clock.receipt())
    write_json(root/'release-source-inventory.json',{'files':sources,'source_sha256':source_digest(sources),'source_review_only':True})
    write_json(root/'checkpoint-storage-plan.json',storage_plan())
    worker_env=worker_environment(fixture=fixture)
    write_json(root/'worker-environment.json',{'format':'owned-rl-child-environment-v1','environment':worker_env,
        'environment_sha256':sha(canonical(worker_env)),'policy':'closed-source-minimal; no inherited paths or credentials'})
    request={'format':'owned-rl-worker-request-v1','config':config,'output_root':str(root),'sources':sources,
             'clock':clock.receipt(),'plan_sha256':plan.sha256,'scope':'source-review-only-unpublishable',
             'worker_environment_sha256':sha(canonical(worker_env))}
    if external_context is not None:
        receipt=context_receipt(external_context)
        request.update(scope=receipt['scope'],bootstrap=receipt)
    ref=write_json(root/'owner-request.json',request)
    external_release=None
    if not fixture:
        from owned_runtime.bootstrap import issue_parent_release
        external_release=issue_parent_release(external_context,request_path=ref['path'],request_sha256=ref['file_sha256'],sources=sources,plan_sha256=plan.sha256,clock=clock)
    read_fd,write_fd=os.pipe();key=os.urandom(32)
    try:
        os.write(write_fd,key);os.close(write_fd);write_fd=None
        argv=[sys.executable,'-I','-B',str(ROOT/'owned_runtime/worker.py'),ref['path'],ref['file_sha256'],str(read_fd)]
        from owned_runtime.supervisor import register_launch
        launch=register_launch(argv,cwd=ROOT,output=root,journal_path=root/'physical-journal.jsonl',auth_key=key,clock=clock,
            request_path=ref['path'],request_sha256=ref['file_sha256'],sources=sources,fixture=fixture,env=worker_env,pass_fds=(read_fd,),_external_release=external_release)
        owned=run_supervised(argv,cwd=ROOT,output=root,journal_path=root/'physical-journal.jsonl',auth_key=key,clock=clock,
            pass_fds=(read_fd,),fixture=fixture,env=worker_env,_launch=launch)

    finally:
        os.close(read_fd)
        if write_fd is not None:os.close(write_fd)
    write_json(root/'outer-closure.json',owned.receipt)
    source_error=None
    try:verify_inventory(sources)
    except Exception as exc:source_error=str(exc)
    inner=owned.receipt.get('inner_closure') or {};result=None;public_score=None;parent_scoring_ref=None;terminal_error=None;parent_lineage_ref=None
    if inner.get('result_ref'):
        try:
            path=Path(inner['result_ref']['path'])
            need(path.resolve().is_relative_to(root) and not path.is_symlink() and path.stat().st_size<=2*1024**3 and
                 file_sha(path)==inner['result_ref']['file_sha256'],'owned result byte binding differs')
            result=json.loads(path.read_text())
        except Exception as exc:
            terminal_error={'phase':'closed-result-read','type':type(exc).__name__,'message':str(exc)[:4096]}
    status=('owned-mechanics-complete-PUBLIC-sealed' if result and result.get('comparison_complete') else 'owned-mechanics-partial-comparison-PUBLIC-sealed') if source_error is None and owned.capability is not None and result and result['status'] in ('owned-comparison-complete-PUBLIC-sealed','owned-partial-comparison-PUBLIC-sealed') else 'stopped-incomplete'
    if external_context is not None and owned.termination_capability is not None:
        from owned_runtime.parent_scoring import persist_parent_lineage
        try:
            parent_lineage_ref=persist_parent_lineage(external_context,root)
            if not json.loads(Path(parent_lineage_ref['path']).read_text())['all_original_bytes_retained']:
                raise ValueError('parent lineage copies incomplete or changed')
        except BaseException as exc:
            terminal_error={'phase':'parent-lineage-retention','type':type(exc).__name__,'message':str(exc)[:4096]}
            status='stopped-incomplete'
    if external_context is not None and status in ('owned-mechanics-complete-PUBLIC-sealed','owned-mechanics-partial-comparison-PUBLIC-sealed'):
        from owned_runtime.parent_scoring import score_parent_public
        try:
            public_score,parent_scoring_ref=score_parent_public(external_context,owned.capability,result['public'],
                sources=plan.sources,config=config,clock=clock,output_root=root)
        except BaseException as exc:
            terminal_error={'phase':'parent-scoring','type':type(exc).__name__,'message':str(exc)[:4096]}
            status='stopped-incomplete'
    if synthetic_score:
        need(fixture,'synthetic scorer fixture never applies to production')
        if status in ('owned-mechanics-complete-PUBLIC-sealed','owned-mechanics-partial-comparison-PUBLIC-sealed'):
            from owned_runtime.public_bridge import score_closed_public
            from experiment_flow.contracts import digest
            challenges={'owned01':{'train':[{'input':[[1]],'output':[[2]]}], 'test':[{'input':[[1]]},{'input':[[3]]}]}}
            gold={'format':'irisx/rl-public-successor-synthetic-gold-v1','challenges_sha256':digest(challenges),'solutions':{'owned01':[[[2]],[[4]]]}}
            goldref=write_json(root/'synthetic-evaluator/synthetic-gold.json',gold)
            try:
                public_score=score_closed_public(owned.capability,result['public'],sources=plan.sources,
                    evaluator_root=root/'synthetic-evaluator',output_root=root/'public-scoring',
                    evaluator_manifest_sha256=goldref['file_sha256'])
            except BaseException as exc:
                terminal_error={'phase':'synthetic-scoring','type':type(exc).__name__,'message':str(exc)[:4096]}
                status='stopped-incomplete'
    checkpoint_export=None
    if status in ('owned-mechanics-complete-PUBLIC-sealed','owned-mechanics-partial-comparison-PUBLIC-sealed'):
        from owned_runtime.storage import export_checkpoint_zip
        try:
            checkpoint_export=export_checkpoint_zip(owned.capability,root/'experiment/checkpoints',root/'checkpoints.zip')
            write_json(root/'checkpoint-zip-descriptor.json',checkpoint_export)
        except BaseException as exc:
            terminal_error={'phase':'checkpoint-export','type':type(exc).__name__,'message':str(exc)[:4096]}
            status='stopped-incomplete'
    answer={'format':'owned-rl-result-v1','status':status,'fixture':fixture,'scope':'source-review-only-unpublishable',
        'production_admitted':False,'source_integrity_error':source_error,'source_sha256':source_digest(sources),'plan_sha256':plan.sha256,
        'clock':clock.receipt(),'outer_closure_ref':{'path':str(root/'outer-closure.json'),'file_sha256':file_sha(root/'outer-closure.json')},
        'result_ref':inner.get('result_ref'),'PUBLIC_score':public_score,'checkpoint_export':checkpoint_export,
        'parent_scoring_ref':parent_scoring_ref,'parent_lineage_ref':parent_lineage_ref,
        'terminal_error':terminal_error,'ARC_or_14B_efficacy_claim':False}
    write_json(root/'owned-result.json',answer)
    from owned_runtime.evidence import seal_artifact_inventory
    from owned_runtime.evidence_zip import export_evidence_only,export_diagnostic_evidence
    destination=root.with_name(root.name+'.evidence.zip')
    terminal_path=Path(str(destination)+'.terminal.json')
    try:
        seal_artifact_inventory(root)
        if status in ('owned-mechanics-complete-PUBLIC-sealed','owned-mechanics-partial-comparison-PUBLIC-sealed'):
            terminal=export_evidence_only(owned.capability,root,destination,terminal_path=terminal_path)
        else:
            terminal=export_diagnostic_evidence(owned.termination_capability,root,destination,terminal_path=terminal_path)
    except BaseException as exc:
        if not terminal_path.exists():
            from owned_runtime.evidence_zip import _write_terminal
            try:
                _write_terminal(terminal_path,{'format':'owned-rl-evidence-terminal-v1','status':'interrupted',
                    'output_root':str(root),'archive_complete':False,'archive':None,'model_success_claim':False,
                    'scientific_goal_met':False,'production_admitted':False,'model_closed':False,
                    'error':{'type':type(exc).__name__,'message':str(exc)[:4096]},
                    'source_sha256':source_digest(sources),'owner_request_sha256':ref['file_sha256'],
                    'original_clock':clock.receipt(),'closure_claim':'none; collection did not complete',
                    'finished_monotonic':time.monotonic()})
            except Exception:
                pass # Missing terminal is reported, never called successful collection.
        terminal={'status':'interrupted','archive_complete':False,
                  'error':{'type':type(exc).__name__,'message':str(exc)[:4096]},
                  'terminal_receipt':None if not terminal_path.is_file() else
                      {'path':str(terminal_path),'sha256':file_sha(terminal_path),'bytes':terminal_path.stat().st_size}}
    # The sealed on-disk result predates export. Its immutable bytes must not be
    # rewritten to create an archive/receipt hash cycle. This return is a handle.
    return {**answer,'terminal_export':terminal}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tiny-proof',action='store_true');parser.add_argument('--output',required=True)
    parser.add_argument('--fixture-window',type=float,default=240.);parser.add_argument('--synthetic-score',action='store_true')
    parser.add_argument('--failure-fixture',choices=['before_load','after_load']);args=parser.parse_args()
    need(args.tiny_proof,'CLI only admits explicitly bounded tiny CPU proof; no production launch command')
    need(60<=args.fixture_window<=300,'fixture wall window60..300')
    config={'fixture':True}
    if args.failure_fixture:config['failure_fixture']=args.failure_fixture
    answer=run_owned(config,args.output,original_epoch=time.time()-42000+args.fixture_window,synthetic_score=args.synthetic_score)
    print(json.dumps(answer,indent=2),flush=True)
    if answer['status']=='stopped-incomplete' or answer['terminal_export'].get('status')!='complete':raise SystemExit(1)

if __name__=='__main__':
    from owned_runtime.runner import main as _main
    _main()
