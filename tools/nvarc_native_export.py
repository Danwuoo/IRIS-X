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


def native_bindings(root, plan, challenges, evidence):
    # Explicit snapshot of code/material gates, checkpoint transcript and reset
    # observations. Missing reset evidence remains null, never inferred success.
    root=Path(root)
    names={'plan.json','challenges.json','worker-receipts.json','hardware.json',
        'model-verification.json','source-verification.json','parent-verification.json',
        'solver.py','arc_loader.py','arc_decoder.py','inspection.py','inspection_helpers.py',
        'nvarc_native_ttt_budget.py','nvarc_native_ttt_schedule.py',
        'tools/nvarc_native_solve_runtime.py','tools/nvarc_native_multitask.py',
        'tools/nvarc_native_submission.py','tools/arc_kaggle_submission.py',
        'tools/nvarc_native_export.py','tools/nvarc_output_lifecycle.py'}
    for key in challenges:
        names.update('tasks/'+key+'/native/'+name for name in (
            'events.jsonl','checkpoint.json','result.json','hardware.json','preparation.json',
            'prepared-rows.json','training-ledger.json','baseline-inventory.json',
            'trained-inventory.json','reset-inventory.json','post-reset-control.json','cache-control.json'))
    inputs={}
    for name in sorted(names):
        path=root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                'confined regular qualification input required')
        inputs[name]=None if not path.exists() else hashlib.sha256(path.read_bytes()).hexdigest()
    return {'run_id':plan['run_id'],'plan_digest':digest(plan),
        'challenges_digest':digest(challenges),'task_counts':{k:len(v['test']) for k,v in challenges.items()},
        'producer_sha256':plan['producer_sha256'],'model_material_digest':plan['model_material_digest'],
        'source_inventory_digest':plan.get('source_inventory_digest'),
        'export_helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'lifecycle_code_sha256':hashlib.sha256(Path(__file__).with_name('nvarc_output_lifecycle.py').read_bytes()).hexdigest(),
        'evidence_digest':digest(evidence),'qualification_inputs_sha256':inputs}


def qualified_values(root, plan, challenges, evidence, tokenizer, context):
    """Strict replay is required even when recovering a previously valid file."""
    bindings=native_bindings(root,plan,challenges,evidence)
    require(parse_json((root/'plan.json').read_bytes())==plan and
        parse_json((root/'challenges.json').read_bytes())==challenges,
        'qualification plan/input snapshot differs')
    submission,audit=build_native_submission(challenges,plan,evidence,root,tokenizer)
    require(native_bindings(root,plan,challenges,evidence)==bindings,
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


def export(root,tokenizer_path):
    context=startup_context()
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
    receipts=parse_json((root/'worker-receipts.json').read_bytes())
    initial=native_bindings(root,plan,challenges,[])['qualification_inputs_sha256']
    evidence=read_task_evidence(root,plan,challenges,receipts)
    require(native_bindings(root,plan,challenges,evidence)['qualification_inputs_sha256']==initial,
        'checkpoint snapshot changed during evidence read')
    bindings,values=qualified_values(root,plan,challenges,evidence,Tokens(),context)
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
    args=parser.parse_args();print(json.dumps(export(args.root,args.tokenizer)))


if __name__=='__main__':main()
