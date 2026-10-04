"""Decision 0059 journaled Kaggle CLI transport. Writes are reserved once.

Uses the installed official executable, with argument arrays and no shell.
Provider uncertainty consumes the reservation; read-only reconciliation is the
only next transport action. No credentials are logged or supplied as arguments.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.nvarc_native_multitask import write,require,digest
from tools.stage_nvarc_official import preflight,sha

CLI=Path('C:/Users/wurre/AppData/Local/Programs/Python/Python312/Scripts/kaggle.exe')
COMPETITION='arc-prize-2026-arc-agi-2'
JOURNAL=ROOT/'.irisx/stage3-official-score-20261005-001'


def timestamp():
    now=datetime.now(timezone.utc)
    return {'utc':now.isoformat(),'taipei':now.astimezone(timezone(timedelta(hours=8))).isoformat()}


def reserve(path,binding):
    """Atomic exclusive creation; no exception or process crash permits resend."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    body=json.dumps(binding,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    with path.open('xb') as stream:
        stream.write(body);stream.flush();os.fsync(stream.fileno())


def invoke(args,label,*,timeout=240):
    require(label.replace('-','').isalnum(),'unambiguous journal label required')
    command=[str(CLI),*args]
    start=timestamp();stdout=JOURNAL/(label+'.stdout');stderr=JOURNAL/(label+'.stderr')
    require(not stdout.exists() and not stderr.exists(),'journal command label already consumed')
    write(JOURNAL/(label+'.command.json'),{'command':command,'cli_version':'2.2.4','started':start,
          'credential_arguments':False,'shell':False})
    try:
        with stdout.open('xb') as out,stderr.open('xb') as err:
            result=subprocess.run(command,stdout=out,stderr=err,timeout=timeout,
                                  env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        code=result.returncode;error=None
    except Exception as exc:
        code=None;error={'type':type(exc).__name__,'message':str(exc)[:1000]}
    receipt={'command':command,'started':start,'completed':timestamp(),'returncode':code,'error':error,
        'stdout_sha256':sha(stdout) if stdout.is_file() else None,'stderr_sha256':sha(stderr) if stderr.is_file() else None,
        'unknown_outcome_for_write':code is None or code!=0}
    write(JOURNAL/(label+'.receipt.json'),receipt)
    return receipt


def accepted_push(package):
    record=json.loads((JOURNAL/'kernel-push.receipt.json').read_bytes())
    text=(JOURNAL/'kernel-push.stdout').read_text(encoding='utf-8')
    candidate=json.loads((package/'candidate-plan.json').read_bytes())
    require(record['returncode']==0 and 'Kernel version 1 successfully pushed.' in text and
        'https://www.kaggle.com/code/'+candidate['kernel_id'] in text and
        'not valid' not in text and 'error' not in text.lower(), 'exact version-one push receipt required')
    return candidate


def completion_preflight(package,output):
    candidate=accepted_push(package);summary=json.loads((output/'official-summary.json').read_bytes())
    terminal=json.loads((output/'terminal.json').read_bytes())
    submission=json.loads((output/'submission.json').read_bytes())
    require(summary['run_id']==candidate['run_id'] and summary['candidate_digest']==digest(candidate) and
        terminal['run_id']==candidate['run_id'] and terminal['outcome']=='export-complete' and
        summary['strict_same_runtime_export_completed'] is True and summary['strict_portable_gpu_gate'] is False and
        summary['paid_usd']==summary['teacher_calls']==0 and summary['official_score'] is None and
        sha(output/'submission.json')==summary['submission_sha256'],'exact private completion/export binding required')
    counts=summary['output_counts'];coverage=summary['coverage']
    require(len(submission)==counts['task_count']==coverage['task_count'] and
        sum(len(v) for v in submission.values())==counts['test_output_count']==coverage['test_count'] and
        coverage['tasks_launched']==coverage['task_count'] and coverage['full_epochs']==coverage['task_count'] and
        coverage['tests_started']==coverage['test_count'] and coverage['all_resets_verified'] is True,
        'formal submission preflight requires every preview task epoch/test and reset; no mostly skipped filler run')
    from tools.arc_kaggle_submission import grid
    for values in submission.values():
        for item in values:
            require(set(item)=={'attempt_1','attempt_2'},'two official attempt slots required')
            grid(item['attempt_1']);grid(item['attempt_2'])
    require(sum(summary['attempt_source_counts'].values())==2*coverage['test_count'],
            'model/filler attempt accounting differs')
    return {'run_id':candidate['run_id'],'candidate_digest':digest(candidate),'kernel':candidate['kernel_id'],
        'version':1,'output_filename':'submission.json','summary_sha256':sha(output/'official-summary.json'),
        'submission_sha256':sha(output/'submission.json'),'preview_coverage':coverage,
        'preview_attempt_source_counts':summary['attempt_source_counts'],
        'hidden_rerun_coverage':'not inferred from preview','strict_portable_gpu_gate':False}


def push(package):
    proof=preflight(package);candidate=json.loads((package/'candidate-plan.json').read_bytes())
    command=['kernels','push','-p',str(package/'kernel'),'-t','42600','--accelerator','NvidiaL4']
    reserve(JOURNAL/'kernel-push.reserved.json',{'action':'private-save-and-run','package':str(package),
        'candidate_digest':proof['candidate_digest'],'manifest_sha256':sha(package/'manifest.json'),
        'command':[str(CLI),*command],'reserved':timestamp(),'paid_usd':0,'provider_retry':False})
    return invoke(command,'kernel-push')


def submit(package,output):
    preflight(package);proof=completion_preflight(package,output)
    # Final quota reconciliation is read-only and recorded before reservation.
    listing=invoke(['competitions','submissions',COMPETITION,'--format','json','--page-size','100'],'submissions-final-before')
    require(listing['returncode']==0,'current submissions must be readable before the sole formal write')
    body=(JOURNAL/'submissions-final-before.stdout').read_text(encoding='utf-8').strip()
    prior=[] if body=='No submissions found' else json.loads(body)
    require(isinstance(prior,list),'current submissions response schema differs')
    today=datetime.now(timezone.utc).date()
    for item in prior:
        date=item.get('date')
        require(not date or datetime.fromisoformat(date.replace('Z','+00:00')).date()!=today,
                'a submission already exists today; do not consume another daily slot')
    message='Stage3 official 001 '+proof['candidate_digest'].removeprefix('sha256:')[:16]
    # The CLI's global client interprets any short -v as verbose. Use the long
    # version flag so kernel binding cannot accidentally enable request logging.
    command=['competitions','submit',COMPETITION,'-f','submission.json','-k',proof['kernel'],'--version','1','-m',message]
    write(JOURNAL/'completion-preflight.json',proof)
    reserve(JOURNAL/'formal-submit.reserved.json',{'competition':COMPETITION,'kernel':proof['kernel'],'version':1,
        'output_filename':'submission.json','candidate_digest':proof['candidate_digest'],'message':message,
        'command':[str(CLI),*command],'reserved':timestamp(),'maximum_formal_submissions':1,'provider_retry':False})
    return invoke(command,'formal-submit')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['push','submit','completion-preflight','status','logs','output','submissions'])
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--output',type=Path)
    parser.add_argument('--label')
    args=parser.parse_args();JOURNAL.mkdir(parents=True,exist_ok=True)
    if args.action=='push':result=push(args.package)
    elif args.action=='submit':result=submit(args.package,args.output)
    elif args.action=='completion-preflight':result=completion_preflight(args.package,args.output)
    else:
        candidate=accepted_push(args.package);require(bool(args.label),'new read journal label required')
        if args.action=='submissions':command=['competitions','submissions',COMPETITION,'--format','json','--page-size','100']
        elif args.action=='output':
            require(args.output is not None and not args.output.exists(),'fresh terminal retrieval directory required')
            command=['kernels','output',candidate['kernel_id'],'-p',str(args.output),
                '--file-pattern','^(submission.json|official-summary.json|terminal.json)$']
        else:command=['kernels',args.action,candidate['kernel_id']]
        result=invoke(command,args.label,timeout=600 if args.action=='output' else 240)
    print(json.dumps(result))


if __name__=='__main__':main()
