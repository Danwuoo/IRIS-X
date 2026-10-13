"""Closed, source-bound successor of the immutable portfolio diagnostic."""
from copy import deepcopy
import math
from tools.arc_qwen_probe_20261012.protocol import require, canonical, digest, file_sha, checked_json

PROTOCOL = {
    'format': 'irisx/true-arc-transfer-protocol-v1', 'model': 'Qwen/Qwen3-14B',
    'revision': '40c069824f4251a91eefaf281ebe4c544efd3e18',
    'precision': 'bf16-base-fp32-lora', 'rank': 8, 'alpha': 16,
    'context_limit': 4096, 'prompt_cap': 3072, 'grid_output_cap': 1024,
    'seed': 1917, 'split_seed': 'irisx-true-arc-transfer-20261012-v1',
    'maximum_seconds': 43200, 'maximum_session_seconds': 43200, 'provider_runtime_seconds':42300,'execution_cutoff_seconds':42000,
    'checkpoint_updates': [64, 256], 'ttt_updates': [0, 8, 16],
    'train_parents': 32, 'dev_parents': 16, 'holdout_parents': 32,
    'ttt_dev_parents': 8, 'ttt_holdout_parents': 8,
    'query_transforms': [0, 1], 'maximum_answers': 2,
    'learning_rate': .0002, 'task_learning_rate': .00005,
    'augmentation': 'eight D4 views, deterministic bijective palettes fixing color0',
    'global_sampler': 'original objective_cycle=[grid]; equal family turns; parent==family',
    'selection': 'sealed dev exact, shape, valid, earlier SFT update; no holdout target',
    'ttt_selection': 'complete outer folds; exact,shape,valid,weighted-NLL,earlier-update; top2 distinct',
    'target_policy': 'last source demonstration held out; original task test fields discarded',
    'ttt_budget': 'all-or-none admission of dev8+holdout8; 16*(D+16) maximum updates,3D fold generations+scores,6*16 query generations',
    'checkpoint_store_maximum_bytes': 2*1024**3,
    'public_solving_admitted': 'conditional-complete167-after-main', 'public_score': None,
    'public_selection':'sealed dev base/SFT64/SFT256 exact-shape-valid-earlierupdate, single frozen method, identity+D4',
    'public_branch_status': 'conditional-offline-solver-and-unchanged-scorer-after-owner-closure',
    'terminal_statuses': ['TRANSFER_COMPLETE', 'TRANSFER_PARTIAL', 'TRANSFER_NOT_ADMITTED', 'TRANSFER_FAILED'],
}


def validate_config(config):
    require(type(config) is dict, 'configuration object required')
    allowed = {'enabled','tiny_cpu','tokenizer_path','tiny_hidden_size','training_root',
        'public_exclusions_path','public_exclusions_sha256','public_solver_root','public_solver_manifest_sha256',
        'public_evaluator_root','public_evaluator_manifest_sha256','model','started_epoch','maximum_seconds',
        'test_failure','test_fixture_dataset','test_calibration_lengths','test_skip_ttt','test_checkpoint_updates','test_generation_cap'}
    require(not set(config)-allowed, 'unknown configuration field')
    require(config.get('enabled') is True, 'explicit enable required')
    tiny=config.get('tiny_cpu',False); require(type(tiny) is bool,'exact tiny Boolean required')
    start=config.get('started_epoch'); require(type(start) in (int,float) and math.isfinite(start) and start>0,'finite actual pre-dispatch epoch required')
    seconds=config.get('maximum_seconds',43200)
    require(type(seconds) is int and 120<=seconds<=43200,'session duration must not exceed12h')
    if not tiny:
        require(seconds==43200,'production session fixed at12h')
        require(not any(k.startswith('test_') or k in ('tokenizer_path','tiny_hidden_size') for k in config),'fixture fields denied in production')
        require(type(config.get('model')) is dict,'production model configuration required')
        require(not any(k.startswith('test_') or k in ('tiny_cpu','probe_fixture_generation_caps') for k in config['model']),'nested fixture fields denied')
        for key in ('training_root','public_exclusions_path','public_exclusions_sha256'):
            require(type(config.get(key)) is str and config[key], 'pinned '+key+' required')
    else:
        require(config.get('test_fixture_dataset') is True,'synthetic source fixture must be explicit')
        require(config.get('test_calibration_lengths') in (None,[128,512]),'unreviewed fixture calibration lengths')
        require(config.get('test_failure') in (None,'before_load','after_load','before_train','output'),'unknown test fault')
        require(config.get('test_checkpoint_updates',[1,2]) in ([1,2],[64,256]),'closed fixture checkpoint choice')
        require(type(config.get('test_generation_cap',4)) is int and 1<=config.get('test_generation_cap',4)<=1024,'fixture output cap')
    result=deepcopy(config)
    if tiny:
        result.setdefault('test_checkpoint_updates',[1,2]);result.setdefault('test_generation_cap',4)
    return result
