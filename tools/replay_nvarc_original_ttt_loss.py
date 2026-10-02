"""Replay hash-gated original formatter/collator over the full long-task views.

Only trusted pinned notebook definitions execute. The Trainer loss method uses
an explicitly artificial tensor/model stub; no Unsloth import or model runs.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic,sha
from irisx.arc_nvarc_source_bundle import verify_bundle
from irisx.arc_nvarc_upstream import source_bundle,qwen_cell
from irisx.arc_nvarc_training import task_local_sequences
from irisx.arc_nvarc_data import visible_task
from irisx.canonical import digest_value
from irisx.errors import ValidationError

PACKAGE=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-long-ttt-002/package-l4'
MODEL=ROOT/'.irisx/nvarc-original/materials/qwen3-published-sft139-20261002-001'


def replay(output):
    if output.exists():raise ValidationError('new immutable loss replay required')
    import numpy as np
    import torch
    from tokenizers import Tokenizer
    started=time.monotonic()
    summary=json.loads((PACKAGE/'stage-summary.json').read_bytes())
    if {p.relative_to(PACKAGE).as_posix():sha(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='stage-summary.json'}!=summary['inventory']:
        raise ValidationError('frozen compatibility proposal bytes differ')
    plan=json.loads((PACKAGE/'plan.json').read_bytes());visible=json.loads((PACKAGE/'visible.json').read_bytes())
    if (digest_value(plan)!=summary['plan_digest'] or plan['source_view_count']!=128 or
            plan['source_input_tokens']!=955392 or plan['source_max_sequence_length']!=7464 or
            len(visible)!=1 or any('output' in item for case in visible.values() for item in case['test'])):
        raise ValidationError('exact source-only complete long-task proposal required')
    proof=json.loads((MODEL/'independent-verification.json').read_bytes());tokenizer_path=MODEL/'model/tokenizer.json'
    if (proof['material_digest']!='sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03' or
            sha(tokenizer_path)!=proof['inventory']['tokenizer.json']['sha256']):
        raise ValidationError('exact original published WordLevel tokenizer required')
    tokenizer=Tokenizer.from_file(str(tokenizer_path))
    class OriginalTokenizer:
        def encode(self,text):return tokenizer.encode(text).ids
    task=next(visible_task(key,value) for key,value in visible.items())
    source=PACKAGE/'source-bundle';verify_bundle(source,plan['source_bundle_digest'])
    with source_bundle(source,plan['source_bundle_digest']):
        loader=qwen_cell('arc_loader.py');formatter=loader.QwenFormatter(OriginalTokenizer())
        dataset=loader.ArcDataset(queries={'view':{'train':task['train'],'test':task['test']}},keys=['view'])
        state=np.random.get_state()
        try:dataset=dataset.augment(n=16,shfl_keys=True,seed=1)
        finally:np.random.set_state(state)
        dataset=dataset.cut_to_len(formatter=formatter,name='text',max_len=8192)
        original=dataset.as_list(formatter)
        rows=task_local_sequences(task,seed=42,augmentation_count=16,source_qwen=True,
            source_augmentation_seed=1,source_max_length=8192)
        if len(original)!=len(rows) or len(rows)!=128 or digest_value(rows)!=plan['source_rows_digest']:
            raise ValidationError('complete original augmented row identity differs')
        collator=qwen_cell('arc_solver.py').QwenDataCollatorForCompletionOnlyLM()
        evidence=[]
        for index,(item,row) in enumerate(zip(original,rows)):
            ids=tokenizer.encode(item['text']).ids
            labels=collator.torch_call([ids])['labels'][0].tolist()
            if ids!=row['input_ids'] or labels!=row['labels']:
                raise ValidationError('original source formatter/tokenizer/completion labels differ at '+str(index))
            evidence.append({'row':index,'original_text_sha256':hashlib.sha256(item['text'].encode()).hexdigest(),
                'input_ids_digest':digest_value(ids),'labels_digest':digest_value(labels),
                'input_tokens':len(ids),'supervised_tokens':sum(x>=0 for x in labels[1:])})
    # Execute only the exact trusted loss class, with explicit artificial inputs.
    binding=json.loads((source/'source-manifest.json').read_bytes())['notebooks']['qwen']
    notebook=source/binding['path']
    if sha(notebook)!=binding['sha256']:raise ValidationError('pinned original loss source differs')
    solver=next(''.join(c['source']).split('\n',1)[1] for c in json.loads(notebook.read_bytes())['cells']
        if ''.join(c.get('source',[])).startswith('%%writefile arc_solver.py'))
    klass=next(node for node in ast.parse(solver).body if isinstance(node,ast.ClassDef) and node.name=='UnslothFixedTrainer')
    if len(klass.body)!=1 or not isinstance(klass.body[0],ast.FunctionDef) or klass.body[0].name!='compute_loss':
        raise ValidationError('only original compute_loss class definition allowed')
    namespace={'UnslothTrainer':type('ArtificialTrainerBase',(),{})}
    exec(compile(ast.Module(body=[klass],type_ignores=[]),str(notebook)+'::UnslothFixedTrainer','exec'),namespace)
    observations=[]
    for processes in (1,4):
        leaf=torch.tensor(2.0,requires_grad=True);source_view=leaf.expand(1)[0]
        stub_calls=[]
        def artificial_model(**inputs):stub_calls.append(inputs);return {'loss':source_view}
        trainer=namespace['UnslothFixedTrainer']();trainer.label_smoother=None
        trainer.accelerator=SimpleNamespace(num_processes=processes)
        loss,outputs=trainer.compute_loss(artificial_model,{'labels':'artificial-fixture'},return_outputs=True)
        if (loss._base is not None or loss.data_ptr()==source_view.data_ptr() or
                float(loss.detach())!=2.0*processes or outputs['loss'] is not source_view or len(stub_calls)!=1):
            raise ValidationError('original view-clone/DDP scaling fixture failed')
        loss.backward()
        if float(leaf.grad)!=processes:raise ValidationError('original view-clone fixture gradient differs')
        observations.append({'num_processes':processes,'loss':float(loss.detach()),'leaf_gradient':float(leaf.grad),
            'cloned_independent_storage':True,'actual_model':False,'artificial_callable_calls':1})
    result={'format':'irisx/nvarc-original-ttt-loss-replay-v1','outcome':'complete-source-mask-replay',
        'proposal_run_id':plan['run_id'],'proposal_plan_digest':digest_value(plan),'source_bundle_digest':plan['source_bundle_digest'],
        'original_notebook_sha256':binding['sha256'],'original_tokenizer_sha256':sha(tokenizer_path),
        'task_id':task['task_id'],'parent_ids':plan['public_task_selection']['parent_ids'],
        'exposure_tags':plan['public_task_selection']['exposure_tags'],'source_rows_digest':digest_value(rows),
        'view_count':len(rows),'input_tokens':sum(x['input_tokens'] for x in evidence),
        'supervised_tokens':sum(x['supervised_tokens'] for x in evidence),'maximum_sequence_length':max(x['input_tokens'] for x in evidence),
        'original_collator_mask_invocations':128,'every_original_input_and_label_equal':True,'rows':evidence,
        'source_collator_scope':'unchanged original mask method; single-example unpadded parent batch substitution',
        'trainer_loss_ast_sha256':hashlib.sha256(ast.dump(klass,include_attributes=False).encode()).hexdigest(),
        'trainer_loss_artificial_observations':observations,'original_trainer_runtime_observed':False,
        'model_calls':0,'optimizer_steps':0,'generation_calls':0,'teacher_calls':0,'external_calls':0,
        'generated_program_executions':0,'paid_usd':0,'correctness_scored':False,'full_long_ttt_completed':False,
        'wall_seconds':time.monotonic()-started}
    atomic(output,result)
    return {'outcome':result['outcome'],'proof_sha256':sha(output),'view_count':len(rows),
        'input_tokens':result['input_tokens'],'supervised_tokens':result['supervised_tokens'],'model_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(replay(parser.parse_args().output)))
