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


def startup_context():
    require(os.environ.get('PYTHONHASHSEED')=='0' and sys.flags.hash_randomization==0,
        'native export needs a fresh interpreter started with PYTHONHASHSEED=0')
    require(os.environ.get('CUDA_VISIBLE_DEVICES','')=='','native export must be CPU only')
    return {'pythonhashseed':'0','hash_randomization_flag':sys.flags.hash_randomization,
        'cpu_only':True,'new_model_calls':0,'python':sys.version.split()[0]}


def export(root,tokenizer_path):
    context=startup_context()
    plan=json.loads((root/'plan.json').read_bytes())
    require(plan['pythonhashseed']==0 and plan['approved'] is True and
        plan.get('export_verification_process')=='fresh-cpu-startup-hashseed-0' and
        plan['export_helper_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'exact admitted CPU export helper binding required')
    from tokenizers import Tokenizer
    tok=Tokenizer.from_file(str(tokenizer_path))
    class Tokens:
        def encode(self,text):return tok.encode(text).ids
        def decode(self,values):return tok.decode(values,skip_special_tokens=False)
    challenges=json.loads((root/'challenges.json').read_bytes())
    receipts=json.loads((root/'worker-receipts.json').read_bytes())
    evidence=read_task_evidence(root,plan,challenges,receipts)
    submission,audit=build_native_submission(challenges,plan,evidence,root,Tokens())
    context.update(run_id=plan['run_id'],plan_digest=digest(plan),
        base_key_hashes={r['task_id']+'_'+str(i):hash(r['task_id']+'_'+str(i))
            for r in evidence for i in range(len(challenges[r['task_id']]['test']))})
    for name,value in (('native-evidence.json',evidence),('submission-audit.json',audit),
            ('submission.json',submission),('export-process.json',context)):
        write(root/name,value)
    return {'export_completed':True,**context}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--tokenizer',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(export(args.root,args.tokenizer)))


if __name__=='__main__':main()
