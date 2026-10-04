"""Private offline four-L4 full-input notebook parent; no provider APIs."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

from tools.nvarc_native_multitask import write,require,digest
from tools.nvarc_official_adapter import runtime_plan,receipt_for,coverage_summary


def execute(root, candidate, raw, started):
    active={};receipts=[];plan=None;phase='source-inventory'
    def save(name,value):write(root/name,value)
    def kill(process):
        if process.poll() is None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=10)
    try:
        require(sys.version_info[:3]==(3,11,13),'original Python 3.11.13 required')
        require(shutil.disk_usage(root).free>=10*1024**3,'at least ten GiB free working space required')
        roots=[Path(p) for p in sys.path if Path(p).is_absolute() and
               Path(p).is_relative_to('/kaggle/usr/lib/notebooks')]
        matches=[p for p in dict.fromkeys(roots) if (p/'qwen3.patch').is_file()]
        require(len(roots)<=32 and len(matches)==1,'exact original dependency mount required')
        dependency=matches[0];binding=json.loads(raw['source_inventory'])
        for name,item in binding.items():
            path=dependency/name
            require(path.stat().st_size==item['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],
                    'original dependency bytes differ: '+name)
        save('source-verification.json',{'root':str(dependency),'inventory':binding,'script_version_id':272622465})
        sys.path.insert(0,str(dependency))
        phase='hardware-inventory'
        import torch
        from hardware_helpers import collect_hardware_inventory
        smi=subprocess.run(['nvidia-smi','--query-gpu=index,name,memory.total,uuid','--format=csv,noheader,nounits'],
                           capture_output=True,text=True,check=True,timeout=30)
        hardware=collect_hardware_inventory(torch,smi.stdout,lambda value:save('hardware-raw.json',value))
        save('hardware.json',{'inventory':hardware,'torch':torch.__version__,'cuda':torch.version.cuda})
        require(len(hardware)==len({r['uuid'] for r in hardware})==4 and
            all(r['name']=='NVIDIA L4' and r['bf16'] for r in hardware),'four distinct BF16 L4s required')
        require(torch.__version__=='2.8.0+cu128' and torch.version.cuda=='12.8','original Torch/CUDA build required')
        mounts=[Path('/kaggle/input/models/sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'),
                Path('/kaggle/input/qwen3_4b_grids15_sft139/transformers/bfloat16/1')]
        models=[p for p in mounts if (p/'config.json').is_file()]
        require(len(models)==1,'exact published SFT139 mount required')
        model=models[0];phase='model-byte-verification';inventory=json.loads(raw['model_inventory'])
        for name,item in inventory.items():
            path=model/name
            with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
            require(path.stat().st_size==item['bytes'] and actual==item['sha256'],'published model bytes differ: '+name)
        save('model-verification.json',{'all_ten_files_verified':True,
            'model_material_digest':candidate['model_material_digest'],'model_mount':str(model),'competition_files_opened':1})
        phase='actual-official-input'
        challenge_path=Path('/kaggle/input/competitions/arc-prize-2026-arc-agi-2/arc-agi_test_challenges.json')
        from tools.arc_kaggle_submission import load_json,challenge_counts
        challenges=load_json(challenge_path);challenge_counts(challenges)
        save('challenges.json',challenges)
        save('input-provenance.json',{'path':str(challenge_path),'sha256':hashlib.sha256(challenge_path.read_bytes()).hexdigest(),
            'opened_files':[challenge_path.name],'test_answers_opened':False,'preview_hash_is_not_a_hidden_input_binding':True})
        from tokenizers import Tokenizer
        from tools.nvarc_native_solve_runtime import load_sources
        import numpy as np
        tok=Tokenizer.from_file(str(model/'tokenizer.json'))
        class Tokens:
            def encode(self,text):return tok.encode(text).ids
            def decode(self,values):return tok.decode(values,skip_special_tokens=False)
        loader,_,_=load_sources(root,SimpleNamespace(no_grad=lambda:lambda f:f),np)
        phase='full-input-native-plan'
        plan,materials=runtime_plan(candidate,challenges,loader,Tokens(),
            candidate['maximum_notebook_wall_seconds']-candidate['packaging_reserve_seconds']-(time.monotonic()-started))
        require(time.monotonic()-started<=candidate['initial_preparation_seconds'],
                'initial full-input preparation exceeded its finite allowance')
        save('plan.json',plan)
        save('parent-verification.json',{'plan_digest':digest(plan),'source_inventory_verified':True,
            'model_material_digest':plan['model_material_digest'],'four_distinct_bf16_l4s':True})
        phase='transient-tensorflow-removal'
        with (root/'dependency-setup.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-m','pip','uninstall','-y','tensorflow'],stdout=log,stderr=subprocess.STDOUT,
                           check=True,timeout=60)
        phase='four-independent-native-task-lanes'
        queues=[list(q) for q in plan['allocation']['queues']]
        receipts=[receipt_for(key) for key in plan['task_order']];by_task={r['task_id']:r for r in receipts}
        save('worker-receipts.json',receipts)
        deadline=started+plan['maximum_notebook_wall_seconds']-plan['packaging_reserve_seconds']
        while active or any(queues):
            for index in range(4):
                if index in active or not queues[index]:continue
                key=queues[index].pop(0);spec=plan['task_specs'][key];receipt=by_task[key]
                remaining=min(spec['child_seconds'],deadline-time.monotonic())
                if remaining<spec['child_seconds']:
                    receipt['status']='session_limit';save('worker-receipts.json',receipts);continue
                directory=root/'tasks'/key;directory.mkdir(parents=True)
                write(directory/'texts.json',materials[key]['texts']);write(directory/'expected-rows.json',materials[key]['rows'])
                environment=dict(os.environ,PYTHONPATH=str(root)+os.pathsep+str(dependency),
                    CUDA_VISIBLE_DEVICES=hardware[index]['uuid'],PYTHONHASHSEED='0',HF_HUB_OFFLINE='1',
                    TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',UNSLOTH_DISABLE_STATISTICS='1',
                    WANDB_DISABLED='true',TOKENIZERS_PARALLELISM='false',PYTHONIOENCODING='utf-8',
                    TRITON_PTXAS_PATH='/usr/local/cuda/bin/ptxas',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',
                    IRIS_NATIVE_CHILD_DEADLINE=str(time.time()+remaining))
                command=[sys.executable,str(root/'inspection.py'),'--plan',str(root/'plan.json'),'--model',str(model),
                    '--dependency',str(dependency),'--solver',str(root/'solver.py'),'--texts',str(directory/'texts.json'),
                    '--rows',str(directory/'expected-rows.json'),'--output',str(directory/'native')]
                receipt.update(status='interrupted_pending',launched=True,reserved_seconds=remaining)
                save('worker-receipts.json',receipts) # reservation before Popen
                stdout=(directory/'stdout.log').open('w',encoding='utf-8');stderr=(directory/'stderr.log').open('w',encoding='utf-8')
                try:
                    process=subprocess.Popen(command,env=environment,cwd=directory,stdout=stdout,stderr=stderr,start_new_session=True)
                    active[index]=(process,key,time.monotonic()+remaining,stdout,stderr)
                except Exception as error:
                    stdout.close();stderr.close()
                    receipt.update(status='worker_crash',error_type=type(error).__name__,error_message=str(error)[:1000])
                    save('worker-receipts.json',receipts)
            for index,(process,key,end,stdout,stderr) in list(active.items()):
                code=process.poll()
                if code is None and time.monotonic()<end:continue
                receipt=by_task[key]
                if code is None:
                    kill(process);code=process.returncode;receipt['status']='timeout'
                else:receipt['status']='complete' if code==0 else 'worker_crash'
                receipt['returncode']=code;stdout.close();stderr.close();del active[index]
                path=root/'tasks'/key/'native/result.json'
                if receipt['status']=='worker_crash' and path.is_file():
                    result=json.loads(path.read_bytes())
                    receipt['status']='oom' if any('out of memory' in r['error_message'].lower() for r in result['failures']) else 'failed'
                save('worker-receipts.json',receipts)
                save('progress.json',{'run_id':plan['run_id'],'finished':sum(r['returncode'] is not None for r in receipts),
                    'total':len(receipts),'active':len(active),'last_task_id':key,'last_status':receipt['status'],
                    'wall_seconds':time.monotonic()-started})
                print(json.dumps({'task':key,'status':receipt['status'],
                    'finished':sum(r['returncode'] is not None for r in receipts),'total':len(receipts)}),flush=True)
            if active:time.sleep(.25)
        phase='strict-fresh-seed0-export'
        remaining=plan['maximum_notebook_wall_seconds']-(time.monotonic()-started)
        environment=dict(os.environ,PYTHONHASHSEED='0',CUDA_VISIBLE_DEVICES='',PYTHONPATH=str(root)+os.pathsep+str(dependency),
                         HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
        with (root/'export.stdout.log').open('w',encoding='utf-8') as stdout,(root/'export.stderr.log').open('w',encoding='utf-8') as stderr:
            subprocess.run([sys.executable,str(root/'tools/nvarc_native_export.py'),'--root',str(root),
                '--tokenizer',str(model/'tokenizer.json')],env=environment,stdout=stdout,stderr=stderr,
                timeout=min(plan['maximum_export_process_seconds'],remaining),check=True,cwd=root)
        coverage=coverage_summary(root,plan,receipts)
        from tools.arc_kaggle_submission import validate_submission
        submission=json.loads((root/'submission.json').read_bytes());audit=json.loads((root/'submission-audit.json').read_bytes())
        counts=validate_submission(challenges,submission)
        summary={'run_id':plan['run_id'],'candidate_digest':digest(candidate),'runtime_plan_digest':digest(plan),
            'input':json.loads((root/'input-provenance.json').read_bytes()),'coverage':coverage,'output_counts':counts,
            'submission_sha256':hashlib.sha256((root/'submission.json').read_bytes()).hexdigest(),
            'audit_sha256':hashlib.sha256((root/'submission-audit.json').read_bytes()).hexdigest(),
            'attempt_source_counts':{'model':sum(row['attempt_sources'].count('model') for row in audit['rows']),
                                    'filler':sum(row['attempt_sources'].count('filler') for row in audit['rows'])},
            'strict_same_runtime_export_completed':True,'strict_portable_gpu_gate':False,
            'official_score':None,'paid_usd':0,'teacher_calls':0,'correctness_scored':False}
        save('official-summary.json',summary)
        # Competition filename lives at working root, copied only after strict export.
        shutil.copyfile(root/'submission.json',root.parent/'submission.json')
        shutil.copyfile(root/'official-summary.json',root.parent/'official-summary.json')
        phase='terminal'
        save('terminal.json',{'run_id':plan['run_id'],'phase':phase,'outcome':'export-complete',
            'wall_seconds':time.monotonic()-started,'worker_receipts_digest':digest(receipts),'paid_usd':0})
        shutil.copyfile(root/'terminal.json',root.parent/'terminal.json')
        return summary
    except BaseException as error:
        save('terminal.json',{'run_id':candidate['run_id'],'phase':phase,'outcome':'failed',
            'error_type':type(error).__name__,'error_message':str(error)[:2000],
            'wall_seconds':time.monotonic()-started,'paid_usd':0})
        shutil.copyfile(root/'terminal.json',root.parent/'terminal.json')
        raise
    finally:
        for process,key,end,stdout,stderr in active.values():
            kill(process);stdout.close();stderr.close()
