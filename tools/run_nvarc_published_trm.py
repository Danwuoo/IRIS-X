"""Bounded published-width CPU TRM load/demo-TTT/inference; no quality scoring."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError


def worker(run):
    import torch
    from tools.nvarc_source import verify as verify_source
    from irisx.arc_nvarc_data import visible_task
    from irisx.arc_nvarc_m3_trm import _source_classes,_batch,_step
    from irisx.arc_nvarc_trm import _decode_trm_tensor
    from irisx.arc_nvarc_trm_checkpoint import load_published_state,published_model_config
    from irisx.arc_nvarc_upstream import SOURCE
    if not re.fullmatch(r'nvarc-overnight-trm-cpu-\d{3}',run):raise ValidationError('new local TRM identity required')
    folder=ROOT/'.irisx/nvarc-original/runs'/run
    if folder.exists():raise ValidationError('local TRM output is immutable')
    material=ROOT/'.irisx/nvarc-original/materials/trm-published-031-20261002'
    acquisition=json.loads((material/'acquisition.json').read_bytes())
    if acquisition['state']!='verified-published-checkpoint-bytes' or acquisition['expected_bytes']!=2159719349:
        raise ValidationError('verified published TRM checkpoint required')
    visible_path=ROOT/'.irisx/nvarc-original/runs/nvarc-overnight-ttt-002/package-l4/visible.json'
    raw=json.loads(visible_path.read_bytes())
    if any(set(item)!={'input'} for value in raw.values() for item in value['test']):
        raise ValidationError('TRM visible test answers forbidden')
    task=visible_task('00576224',raw['00576224']);config=published_model_config()
    plan={'format':'irisx/nvarc-published-trm-cpu-v1','run_id':run,'owner_decision':'Decision 0053',
        'checkpoint_sha256':acquisition['sha256'],'dataset':'cpmpml/arc-prize-trm-031/1','file':'step_220708',
        'visible_digest':digest_value(task),'model_config':config,'maximum_optimizer_steps':1,
        'maximum_inference_forwards':10,'maximum_wall_seconds':600,'maximum_paid_usd':0,
        'maximum_teacher_calls':0,'contains_evaluator_truth':False,
        'exposure':'original mixed-data checkpoint and repeated public tuning task; not clean holdout'}
    folder.mkdir(parents=True);(folder/'plan.json').write_bytes(canonical_bytes(plan,newline=True))
    started=time.monotonic();phase='source-verification'
    def emit(event,**values):
        with (folder/'events.jsonl').open('ab') as stream:
            stream.write(canonical_bytes({'event':event,'elapsed_seconds':time.monotonic()-started,**values},newline=True))
    emit(phase)
    try:
        torch.set_num_threads(4);torch.manual_seed(44)
        proof=verify_source(SOURCE,json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes()))
        (folder/'source-verification.json').write_bytes(canonical_bytes(proof,newline=True))
        phase='published-checkpoint-load';emit(phase)
        model_cls,loss_cls,sparse_cls,adam_cls=_source_classes(SOURCE/'NVARC/external/TinyRecursiveModels')
        model=loss_cls(model_cls(config),loss_type='stablemax_cross_entropy')
        loaded=load_published_state(model,material/'step_220708',acquisition['sha256'])
        (folder/'load-observation.json').write_bytes(canonical_bytes(loaded,newline=True))
        initial=copy.deepcopy(model.state_dict())
        phase='one-public-demo-ttt-step';emit(phase)
        demo=task['train'][0];train_batch=_batch(demo['input'],demo['output'],identifier=0)
        sparse=sparse_cls(model.model.puzzle_emb.buffers(),world_size=1,lr=.01,weight_decay=.1)
        adam=adam_cls(model.parameters(),lr=.0001,weight_decay=0.,betas=(.9,.95))
        loss,nonzero=_step(model,train_batch,[sparse,adam])
        changed=[name for name,value in model.state_dict().items() if not torch.equal(value,initial[name])]
        if not changed:raise ValidationError('published-width TRM demo TTT did not change state')
        del sparse,adam
        emit('optimizer-returned',loss=loss,changed_state_tensors=len(changed),nonzero_gradient_parameters=nonzero)
        phase='visible-test-inference';emit(phase)
        model.eval();batch=_batch(task['test'][0]['input'],None,identifier=0);calls=0
        with torch.inference_mode():
            carry=model.model.initial_carry(batch)
            while calls<10:
                carry,outputs=model.model(carry=carry,batch=batch);calls+=1
                if not bool(torch.isfinite(outputs['logits']).all()):raise ValidationError('TRM inference logits nonfinite')
                if bool(carry.halted.all()):break
            if not bool(carry.halted.all()):raise ValidationError('TRM ACT horizon did not terminate')
            prediction=outputs['logits'].argmax(-1)[0].tolist()
        try:candidate=_decode_trm_tensor(prediction);status='candidate'
        except ValidationError:candidate=None;status='missing-candidate'
        model.load_state_dict(initial,strict=True)
        if any(not torch.equal(value,initial[name]) for name,value in model.state_dict().items()):
            raise ValidationError('published-width TRM task reset differs')
        result={'format':'irisx/nvarc-published-trm-cpu-result-v1','run_id':run,'plan_digest':digest_value(plan),
            'checkpoint_load':loaded,'model_config':config,'task_id':task['task_id'],'test_index':0,
            'ttt_optimizer_steps':1,'ttt_input_tokens':int(train_batch['inputs'].numel()),
            'ttt_supervised_tokens':int((train_batch['labels']!=-100).sum()),'ttt_loss':loss,
            'changed_state_tensors':len(changed),'nonzero_gradient_parameters':nonzero,
            'inference_forwards':calls,'act_halted':True,'raw_prediction':prediction,'candidate':candidate,
            'candidate_status':status,'reset_to_published_state_exact':True,'contains_evaluator_truth':False,
            'correctness_scored':False,'teacher_calls':0,'original_scale_training_verified':False,
            'original_notebook_v18_verified':False,'original_bf16_numerical_parity':False,
            'wall_seconds':time.monotonic()-started}
        (folder/'result.json').write_bytes(canonical_bytes(result,newline=True));emit('complete')
        print(json.dumps({key:value for key,value in result.items() if key!='raw_prediction'}),flush=True)
    except BaseException as error:
        (folder/'failure.json').write_bytes(canonical_bytes({'run_id':run,'plan_digest':digest_value(plan),
            'phase':phase,'error_type':type(error).__name__,'error_message':str(error)[:1200],
            'contains_evaluator_truth':False},newline=True));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('run','worker'));parser.add_argument('--run',required=True)
    args=parser.parse_args()
    if args.action=='worker':worker(args.run)
    else:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker','--run',args.run])
        try:raise SystemExit(process.wait(timeout=600))
        finally:
            if process.poll() is None:
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                process.wait(timeout=15)
