"""Destroy the original backend before one fresh, disk-only inference check."""
from copy import deepcopy
import gc
from pathlib import Path
import time
import weakref
from .protocol import require,digest
from .checkpoints import load_branch_checkpoint,inspect_checkpoint
from .experiment import _parity_probe
from tools.arc_learning_agent_20261011.budget import atomic_json


def dispose_backend(model,trainer):
    reference=weakref.ref(model.model)
    model.close()
    raw=trainer.trainer
    raw.model=None;raw.parameters.clear();raw.optimizer=raw.scheduler=None
    raw._training_snapshots.clear();raw._snapshots.clear()
    gc.collect()
    require(reference() is None,'old backend parameters remain live before fresh construction')
    import torch
    if torch.cuda.is_available():torch.cuda.empty_cache()
    return {'old_model_destroyed':True,'old_adapter_and_optimizer_references_cleared':True}


def verify_fresh_reload(model,trainer,*,factory,dataset,report,policy,ledger,output,deadline):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    require(report['status']=='PORTFOLIO_COMPLETE','complete candidate experiment required before fresh reload')
    ref=deepcopy(report['reload_reference'])
    require(ref is not None and ref['branch_id']=='program_lora','fixed program16 reload reference required')
    records=[r for r in dataset['records'] if r['kind']=='program']
    require(digest(records)==ref['records_sha256'],'fresh reload training records changed')
    before=dict(ledger.used);start=time.monotonic();new_model=new_trainer=None
    counters={'model':model._counter,'trainer':trainer._counter}
    require(all(type(v) is int and v>=0 for v in counters.values()) and not ledger.pending,'closed monotone physical counters required')
    receipt={'format':'irisx/portfolio-fresh-backend-reload-v1','status':'started','verified':False,
        'checkpoint_manifest_sha256':ref['checkpoint']['manifest_sha256'],'physical_usage_before':before}
    atomic_json(root/'receipt.json',receipt)
    try:
        require(time.monotonic()<deadline,'fresh reload deadline before destruction')
        receipt['disposal']=dispose_backend(model,trainer);atomic_json(root/'receipt.json',receipt)
        new_model,new_trainer=factory()
        require(new_model.ledger is ledger and new_trainer.ledger is ledger,'fresh backend must retain the original physical ledger')
        require(new_model._counter==new_trainer._counter==0,'fresh wrapper counters must be unused')
        new_model._counter=counters['model'];new_trainer._counter=counters['trainer']
        receipt['physical_event_counters_retained']=counters
        require(time.monotonic()<deadline,'fresh model loaded after deadline')
        new_trainer.trainer.freeze_decoder_identity(policy)
        new_trainer.trainer.config['split_manifest']=dataset['manifest']
        manifest=inspect_checkpoint(ref['checkpoint']['path'],expected_manifest_sha256=ref['checkpoint']['manifest_sha256'])
        require(manifest['update']==16,'fresh reload must use predeclared update16')
        loaded=load_branch_checkpoint(new_trainer,ref['checkpoint']['path'],branch_id='program_lora',records=records,
            expected_manifest_sha256=ref['checkpoint']['manifest_sha256'],provenance=ref['provenance'])
        observed=_parity_probe(new_model,ref['canary_case'],{ref['canary_case']['case_id']:ref['canary_target']},root/'behavior',deadline)
        require(observed==ref['expected'],'fresh backend disk reload token/NLL behavior differs')
        require(all(ledger.used[k]>=v for k,v in before.items()),'fresh reload refunded physical work')
        receipt.update(status='complete',verified=True,loaded=loaded,observed=observed,expected=ref['expected'],
            model_identity=new_model.identity,hardware=new_model.hardware,
            physical_usage={k:ledger.used[k]-v for k,v in before.items()},elapsed_seconds=time.monotonic()-start,
            full14b_verified=new_model.config.get('tiny_cpu') is not True,
            cpu_fixture_only=new_model.config.get('tiny_cpu') is True)
        atomic_json(root/'receipt.json',receipt)
        return new_model,new_trainer,receipt
    except BaseException as exc:
        receipt.update(status='failed',error=type(exc).__name__+': '+str(exc)[:1024],
            physical_usage={k:ledger.used[k]-v for k,v in before.items()},elapsed_seconds=time.monotonic()-start)
        atomic_json(root/'receipt.json',receipt)
        if new_model is not None:
            try:dispose_backend(new_model,new_trainer)
            except BaseException:new_model.close()
        raise
