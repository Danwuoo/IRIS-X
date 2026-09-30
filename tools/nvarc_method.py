"""Offline source-recipe audit, corpus freezing and inert comparison preparation."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from irisx.arc_nvarc_corpus import FrozenSourceSequenceStore, freeze_source_corpus, sha_file
from irisx.arc_nvarc_data import visible_task
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError

CONTRACT = ROOT / 'trials/arc-agi-2-qwen35-nvarc/configs/method-contract-20260930.json'
SOURCE = ROOT / '.irisx/arc-agi-2/qwen35-nvarc/source'
CODE = ('src/irisx/arc_nvarc_source_recipe.py','src/irisx/arc_nvarc_corpus.py',
        'src/irisx/arc_nvarc_training.py','src/irisx/arc_nvarc_data.py',
        'src/irisx/arc_nvarc_candidates.py','src/irisx/arc_nvarc_representation.py',
        'src/irisx/arc_nvarc_upstream.py','tests/nvarc_method_strict.py',
        'tests/nvarc_source_differential.py','tests/test_arc_nvarc_ml.py',
        'tools/nvarc_method.py','tools/nvarc_ml_profile.py')


def code_binding():
    return {name:sha_file(ROOT/name) for name in CODE}


def upstream_recipe(source: Path):
    """Read effective shell overrides and notebook literal dictionaries; never run cells."""
    from omegaconf import OmegaConf
    from irisx.arc_nvarc_upstream import qwen_cell
    from irisx.arc_nvarc_source_recipe import SourceTextTokenizer
    config = OmegaConf.to_container(OmegaConf.load(source/'NVARC/ARChitects/sft_mg.yaml'),resolve=True)
    script = (source/'NVARC/ARChitects/run_sft_4b.sh').read_text(encoding='utf-8')
    for key,value in re.findall(r'((?:sft|policy|cluster)\.[\w.]+)=([^\s\\]+)',script):
        if '$' in value:
            continue
        parts = key.split('.')
        target = config
        for part in parts[:-1]:
            target = target[part]
        try:
            target[parts[-1]] = ast.literal_eval(value)
        except (ValueError,SyntaxError):
            target[parts[-1]] = value.strip('"')
    notebook_path = source/'kaggle-qwen/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb'
    notebook = json.loads(notebook_path.read_bytes())
    found = {}
    for cell in notebook['cells']:
        text = ''.join(cell.get('source',[]))
        if 'train_args = dict(' not in text:
            continue
        if text.startswith('%%writefile '):
            text = text.split('\n',1)[1]
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node,ast.Assign) or len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name):
                continue
            name = node.targets[0].id
            if name in ('peft_params','train_args') and isinstance(node.value,ast.Call):
                found[name] = {x.arg:ast.literal_eval(x.value) for x in node.value.keywords}
            if name == 'max_seq_length':
                found[name] = ast.literal_eval(node.value)
    optimizer = config['policy']['megatron_cfg']['optimizer']
    scheduler = config['policy']['megatron_cfg']['scheduler']
    return {'sft':{'learning_rate':optimizer['lr'],'minimum_learning_rate':optimizer['min_lr'],
        'warmup_initial_learning_rate':scheduler['lr_warmup_init'],
        'warmup_steps':scheduler['lr_warmup_iters'],'schedule_steps':scheduler['lr_decay_iters'],
        'optimizer_betas':[optimizer['adam_beta1'],optimizer['adam_beta2']],
        'optimizer_eps':optimizer['adam_eps'],'weight_decay':optimizer['weight_decay'],
        'clip_grad_norm':optimizer['clip_grad'],
        'original_optimizer_steps':config['sft']['max_num_steps'],
        'original_global_batch_size':config['policy']['train_global_batch_size'],
        'sources':[Path(x).name for x in config['data']['train_dataset_path']]},
        'ttt':found,'maximum_new_tokens':qwen_cell('arc_loader.py').QwenFormatter(SourceTextTokenizer()).max_new_tokens(),
        'notebook_sha256':sha_file(notebook_path)}


def audit(*, corpus: Path | None=None, proof: Path | None=None):
    contract = json.loads(CONTRACT.read_bytes())
    subprocess.run([sys.executable,str(ROOT/'tools/nvarc_source.py'),'verify'],
                   check=True,stdout=subprocess.DEVNULL)
    original = upstream_recipe(SOURCE)
    source_manifest = json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes())
    if source_manifest['git']['NVARC']['commit'] != contract['source']['nvarc_commit']:
        raise ValidationError('method NVARC commit binding differs')
    if original['notebook_sha256'] != contract['source']['qwen_notebook_sha256']:
        raise ValidationError('method notebook binding differs')
    for key,value in original['sft'].items():
        if contract['sft'][key] != value:
            raise ValidationError('effective source SFT contract differs: '+key)
    mapping = {'rank':'r','alpha':'lora_alpha','use_rslora':'use_rslora'}
    for key,original_key in mapping.items():
        if contract['ttt'][key] != original['ttt']['peft_params'][original_key]:
            raise ValidationError('source LoRA contract differs: '+key)
    for key in ('learning_rate','warmup_ratio','seed'):
        if contract['ttt'][key] != original['ttt']['train_args'][key]:
            raise ValidationError('source TTT training contract differs: '+key)
    if (contract['ttt']['max_sequence_length'] != original['ttt']['max_seq_length'] or
            contract['candidate']['maximum_new_tokens'] != original['maximum_new_tokens']):
        raise ValidationError('source context or reply reservation differs')
    corpus_ready = False
    missing = []
    corpus_digest = None
    if corpus is not None:
        store = FrozenSourceSequenceStore(corpus)
        corpus_digest = store.data_digest
        corpus_ready = store.manifest['material_class'] == 'source-material'
        if not corpus_ready:
            missing.append('Synthetic fixture corpus cannot satisfy actual training-data readiness.')
    else:
        missing.append('Actual six-source corpus, closed inventories and trusted parent/exposure lineage are absent.')
    proof_ready = False
    if proof is not None:
        result = json.loads(proof.read_bytes())
        proof_ready = (result.get('format')=='irisx/nvarc-method-local-proof-v1' and
            result.get('contract_digest')==digest_value(contract) and result.get('code_binding')==code_binding() and
            result.get('exit_code')==0 and result.get('scope')=='source-differential-and-tiny-actual-model-only' and
            sha_file(proof.parent/result['log_path'])==result['log_sha256'])
        if not proof_ready:
            raise ValidationError('local reference proof is stale or mismatched')
    else:
        missing.append('Current-code source differential and tiny actual-model proof has not been supplied.')
    return {'format':'irisx/nvarc-method-readiness-v1','contract_digest':digest_value(contract),
        'source_ready':True,'local_reference_verified':proof_ready,'corpus_ready':corpus_ready,
        'corpus_digest':corpus_digest,'bounded_training_preconditions_met':corpus_ready and proof_ready,
        'full_method_runtime_verified':False,'full_scale_sft_verified':False,
        'quality_comparison_ready':False,'missing':missing,
        'retained_eight_step_export_qualifies_as_full_sft':False,
        'explicit_differences':contract['explicit_differences'],
        'external_allowances':contract['external_allowances'],
        'note':'Advisory local readiness; this report never authorizes execution.'}


def prepare_comparison(output: Path, *, corpus: Path | None=None, proof: Path | None=None):
    readiness = audit(corpus=corpus,proof=proof)
    if output.exists():
        raise ValidationError('comparison output identity must be new')
    old = json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-small.json').read_bytes())
    excluded = {x['id'] for x in old['train']+old['dev']}
    if corpus is not None:
        store = FrozenSourceSequenceStore(corpus)
        excluded.update(store.parent_ids)
    official = SOURCE/'NVARC/external/ARC-AGI-2/data/training'
    paths = sorted((p for p in official.glob('*.json') if p.stem not in excluded),
        key=lambda p:hashlib.sha256(('nvarc-method-dev-20260930:'+p.stem).encode()).hexdigest())[:8]
    if len(paths)!=8:
        raise ValidationError('insufficient separate public development parents')
    visible = {}
    for path in paths:
        task = visible_task(path.stem,json.loads(path.read_bytes()))
        visible[path.stem] = {'train':task['train'],'test':task['test']}
    output.mkdir(parents=True)
    (output/'dev-visible.json').write_bytes(canonical_bytes(visible,newline=True))
    contract = json.loads(CONTRACT.read_bytes())
    plan = {'format':'irisx/nvarc-method-comparison-proposal-v1',
        'run_id':'nvarc-source-method-dev-proposal-001','approved':False,
        'status':'inert-materials-blocked' if not readiness['bounded_training_preconditions_met'] else 'inert-review-required',
        'question':'Does a newly trained six-source compact checkpoint add correct candidate coverage, and does a complete source TTT epoch add further coverage?',
        'arms':['compact-base','new-source-SFT','new-source-SFT-plus-source-epoch-TTT'],
        'contract_digest':readiness['contract_digest'],'corpus_digest':readiness['corpus_digest'],
        'dev_parent_ids':sorted(visible),'test_count':sum(len(t['test']) for t in visible.values()),
        'dev_visible_sha256':sha_file(output/'dev-visible.json'),
        'excluded_pilot_parent_ids':sorted(x['id'] for x in old['train']+old['dev']),
        'development_exposure':'New relative to the retained 16-parent pilot/ABC set; broader published-data exposure still requires audit. Not a fresh holdout.',
        'candidate':contract['candidate'],'adaptation':contract['ttt'],
        'sft_source_recipe':contract['sft'],
        'training_budget_status':'Steps/tokens/sequence/batch and session limits must be fixed after actual corpus and resource measurement; no runtime budget is approved.',
        'metrics':['per-test exact pass@1','per-test exact pass@2','candidate-pool coverage','task-all-correct','missing/invalid','time/memory/steps/tokens/forwards'],
        'evaluator':'Separate local evaluator only; no labels or answer-derived fields in visible input.',
        'maximum_generation_calls_if_reviewed':len(visible)*3*contract['candidate']['maximum_calls_per_task'],
        'external_allowances':contract['external_allowances'],'readiness':readiness}
    (output/'proposal.json').write_bytes(canonical_bytes(plan,newline=True))
    return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ('audit','prepare-comparison'):
        p=commands.add_parser(name)
        p.add_argument('--corpus',type=Path)
        p.add_argument('--proof',type=Path)
        p.add_argument('--output',type=Path,required=True)
    p=commands.add_parser('freeze-corpus')
    p.add_argument('--spec',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='freeze-corpus':
        report=freeze_source_corpus(args.spec,args.output)
    elif args.command=='prepare-comparison':
        report=prepare_comparison(args.output,corpus=args.corpus,proof=args.proof)
    else:
        report=audit(corpus=args.corpus,proof=args.proof)
        if args.output.exists():
            raise ValidationError('readiness output must be new')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(canonical_bytes(report,newline=True))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
