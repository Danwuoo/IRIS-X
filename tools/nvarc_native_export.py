"""Strict CPU export in a fresh interpreter with startup PYTHONHASHSEED=0.

Only retained model transcripts are replayed; no model is loaded or invoked.
Changing os.environ inside an already running notebook cannot reset hash().
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.nvarc_native_multitask import digest,write
from tools.nvarc_native_solve_runtime import require
from tools.nvarc_native_submission import read_task_evidence,build_native_submission
from tools.nvarc_output_lifecycle import GenerationStore
from tools.arc_kaggle_submission import parse_json


def native_bindings(root, plan, challenges, evidence, *, test_allocations=None):
    # Explicit snapshot of code/material gates, checkpoint transcript and reset
    # observations. Missing reset evidence remains null, never inferred success.
    root=Path(root)
    names={'plan.json','challenges.json','worker-receipts.json','hardware.json',
        'model-verification.json','source-verification.json','parent-verification.json',
        'solver.py','arc_loader.py','arc_decoder.py','inspection.py','inspection_helpers.py',
        'nvarc_native_ttt_budget.py','nvarc_native_ttt_schedule.py',
        'tools/nvarc_native_solve_runtime.py','tools/nvarc_native_multitask.py',
        'tools/nvarc_native_submission.py','tools/arc_kaggle_submission.py',
        'tools/nvarc_native_export.py','tools/nvarc_output_lifecycle.py',
        'tools/nvarc_allocation_transport.py','tools/nvarc_public_eval.py','hardware_helpers.py',
        'tools/nvarc_calibration_gate.py','tools/nvarc_source_verification.py','source-verification-prepare.json'}
    for key in challenges:
        names.update('tasks/'+key+'/native/'+name for name in (
            'events.jsonl','checkpoint.json','result.json','hardware.json','preparation.json',
            'prepared-rows.json','training-ledger.json','native-schedule.json','baseline-inventory.json',
            'trained-inventory.json','reset-inventory.json','post-reset-control.json','cache-control.json'))
    inputs={}
    for name in sorted(names):
        path=root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                'confined regular qualification input required')
        inputs[name]=None if not path.exists() else hashlib.sha256(path.read_bytes()).hexdigest()
    result={'run_id':plan['run_id'],'plan_digest':digest(plan),
        'challenges_digest':digest(challenges),'task_counts':{k:len(v['test']) for k,v in challenges.items()},
        'producer_sha256':plan['producer_sha256'],'model_material_digest':plan['model_material_digest'],
        'source_inventory_digest':plan.get('source_inventory_digest'),
        'export_helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'lifecycle_code_sha256':hashlib.sha256(Path(__file__).with_name('nvarc_output_lifecycle.py').read_bytes()).hexdigest(),
        'evidence_digest':digest(evidence),'qualification_inputs_sha256':inputs}
    if test_allocations is not None: result['admitted_test_allocations_digest']=digest(test_allocations)
    return result


def qualified_values(root, plan, challenges, evidence, tokenizer, context, *, test_allocations=None):
    """Strict replay is required even when recovering a previously valid file."""
    bindings=native_bindings(root,plan,challenges,evidence,test_allocations=test_allocations)
    require(parse_json((root/'plan.json').read_bytes())==plan and
        parse_json((root/'challenges.json').read_bytes())==challenges,
        'qualification plan/input snapshot differs')
    options={} if test_allocations is None else {'test_allocations':test_allocations}
    submission,audit=build_native_submission(challenges,plan,evidence,root,tokenizer,**options)
    require(native_bindings(root,plan,challenges,evidence,test_allocations=test_allocations)==bindings,
        'qualification inputs changed during strict replay')
    context.update(run_id=plan['run_id'],plan_digest=digest(plan),
        base_key_hashes={r['task_id']+'_'+str(i):hash(r['task_id']+'_'+str(i))
            for r in evidence for i in range(len(challenges[r['task_id']]['test']))})
    return bindings, {'native-evidence.json':evidence,'submission-audit.json':audit,
                     'submission.json':submission,'export-process.json':context}


def startup_context():
    require(os.environ.get('PYTHONHASHSEED')=='0' and sys.flags.hash_randomization==0,
        'native export needs a fresh interpreter started with PYTHONHASHSEED=0')
    require(os.environ.get('CUDA_VISIBLE_DEVICES','')=='','native export must be CPU only')
    return {'pythonhashseed':'0','hash_randomization_flag':sys.flags.hash_randomization,
        'cpu_only':True,'new_model_calls':0,'python':sys.version.split()[0]}


def export(root,tokenizer_path, *, test_allocations=None, caller_admissions=None,
           caller_admissions_sha256=None, validate_only=False, verify_committed=False, require_tasks=None):
    context=startup_context()
    require(not verify_committed or validate_only, 'committed verification is a read-only replay option')
    plan=parse_json((root/'plan.json').read_bytes())
    require(plan['pythonhashseed']==0 and plan['approved'] is True and
        plan.get('export_verification_process')=='fresh-cpu-startup-hashseed-0' and
        plan['export_helper_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'exact admitted CPU export helper binding required')
    require(plan.get('output_lifecycle_sha256')==hashlib.sha256(
        Path(__file__).with_name('nvarc_output_lifecycle.py').read_bytes()).hexdigest(),
        'exact admitted output lifecycle binding required')
    from tokenizers import Tokenizer
    tok=Tokenizer.from_file(str(tokenizer_path))
    class Tokens:
        def encode(self,text):return tok.encode(text).ids
        def decode(self,values):return tok.decode(values,skip_special_tokens=False)
    challenges=parse_json((root/'challenges.json').read_bytes())
    if caller_admissions is not None or caller_admissions_sha256 is not None:
        from tools.nvarc_allocation_transport import load_caller_receipt
        require(test_allocations is None, 'one independent caller admission input required')
        test_allocations=load_caller_receipt(caller_admissions,caller_admissions_sha256,plan,challenges)
        context.update(caller_admission_receipt_sha256=caller_admissions_sha256,
                       caller_receipt_is_gpu_timing_attestation=False)
    receipts=parse_json((root/'worker-receipts.json').read_bytes())
    initial=native_bindings(root,plan,challenges,[])['qualification_inputs_sha256']
    evidence=read_task_evidence(root,plan,challenges,receipts)
    if caller_admissions is not None:
        from tools.nvarc_allocation_transport import validate_caller_deadlines
        validate_caller_deadlines(evidence,test_allocations,plan,challenges)
    require(native_bindings(root,plan,challenges,evidence)['qualification_inputs_sha256']==initial,
        'checkpoint snapshot changed during evidence read')
    bindings,values=qualified_values(root,plan,challenges,evidence,Tokens(),context,test_allocations=test_allocations)
    if require_tasks:
        from tools.nvarc_calibration_gate import require_task_gates
        context['mandatory_task_gates']=require_task_gates(root,plan,challenges,evidence,Tokens(),require_tasks)
        require(native_bindings(root,plan,challenges,evidence,test_allocations=test_allocations)==bindings,
                'qualification inputs changed during mandatory calibration gates')
    if caller_admissions is not None:
        require(load_caller_receipt(caller_admissions,caller_admissions_sha256,plan,challenges)==test_allocations,
                'caller admission receipt changed during strict replay')
    if validate_only:
        if verify_committed:
            store=GenerationStore(root,'native',bindings)
            _,bodies=store.read();store.verify_projection()
            previous={name:parse_json(body) for name,body in bodies.items()}
            require(all(previous[name]==value for name,value in values.items() if name!='export-process.json'),
                    'committed native output differs from independent strict replay')
            require({k:v for k,v in previous['export-process.json'].items() if k!='python'}==
                    {k:v for k,v in context.items() if k!='python'},
                    'committed native export identity differs from independent replay')
        return {'strict_replay_validated':True,'output_published':False,
                'committed_projection_verified':verify_committed,**context}
    store=GenerationStore(root,'native',bindings)
    if (root/'output-commit.json').exists():
        def revalidate(manifest,previous):
            require(previous==values and manifest['outcomes']['evidence_qualified'] is True,
                    'strict recovered generation differs from replay')
        store.recover(revalidate)
    else:
        store.publish(values,evidence_qualified=True)
    return {'export_completed':True,**context}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--tokenizer',type=Path,required=True)
    parser.add_argument('--caller-admissions',type=Path)
    parser.add_argument('--caller-admissions-sha256')
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--verify-committed',action='store_true')
    parser.add_argument('--require-task-gates',action='append')
    args=parser.parse_args();print(json.dumps(export(args.root,args.tokenizer,
        caller_admissions=args.caller_admissions,caller_admissions_sha256=args.caller_admissions_sha256,
        validate_only=args.validate_only,verify_committed=args.verify_committed,require_tasks=args.require_task_gates)))


if __name__=='__main__':main()
