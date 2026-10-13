"""Fixed, probe-only experiment and closed configuration contracts."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

PROTOCOL = {
    'format': 'irisx/qwen14b-learning-probe-protocol-v3',
    'successor_experiment': True, 'cache_admission_policy_changed': True,
    'public_effectiveness_gate_changed': False, 'numerical_tolerances_changed': False,
    'scope': 'authored train controls and exposed development only',
    'model': 'Qwen/Qwen3-14B', 'revision': '40c069824f4251a91eefaf281ebe4c544efd3e18',
    'precision': 'bf16-base-fp32-lora', 'rank': 8, 'alpha': 16,
    'context_limit': 2048, 'prompt_cap': 1792, 'grid_output_cap': 256, 'program_output_cap': 256,
    'batch_size': 1, 'seed': 1917, 'maximum_probe_seconds': 21600,
    'material_clock_override': {'contract_path':'materials/qwen14b/material-contract.json',
        'contract_sha256':'8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0',
        'sole_overridden_field':'probe_bounds.maximum_probe_seconds', 'historical_value':10800,
        'successor_value':21600, 'global_maximum_seconds':43200, 'all_other_material_clauses_unchanged':True},
    'selectable_science_profiles':['pilot-cached-13','pilot-full-prefix-13'],
    'reference_only_science_profiles':['full-cache-16'],
    'terminal_statuses':['PROBE_PILOT_COMPLETE','PROBE_DIAGNOSTICS_ONLY','PROBE_FAILED'],
    'maximum_session_seconds': 43200, 'maximum_load_seconds': 1800,
    'length_ladder': [128, 512, 2048], 'updates_per_rung': 1,
    'branches': ['frozen_base', 'grid_lora', 'program_lora'],
    'checkpoint_updates': [8, 16], 'maximum_updates_per_branch': 16,
    'maximum_completion_tokens_per_branch': 32768,
    'learning_rate': 0.0002, 'warmup_updates': 4, 'schedule_updates': 32,
    'dev_native_lengths': {'training-dev:b1948b0a':[228,21,249], 'training-dev:e9c9d9a1':[1307,306,1613], 'training-dev:53b68214':[546,110,656], 'training-dev:cce03e0d':[333,90,423]},
    'dev_nll_eligible_case_ids':['training-dev:b1948b0a','training-dev:53b68214','training-dev:cce03e0d'],
    'dev_nll_exclusion': 'e9c9d9a1 requires306native completion tokens includingEOS; fixed256cap preserved; full4exact/program denominator retained',
    'selection': ['exposed_dev_grid_exact_plus_program_exact', 'lower_exposed_dev_grid_nll', 'earlier_update'],
    'train_families': ['identity', 'reverse-columns', 'transpose', 'reverse-rows', 'recolor-one-two', 'repeat-columns'],
    'transpose_exposure': 'new explicitly trained control after observed v9 untrained failure; not untouched',
    'base_representation_diagnostic': 'omitted in both selectable pilots;16-case representation retained only in nonselectable historical reference profile',
    'train_control_interpretation': 'explicitly trained; no held-out generalization claim',
    'authored_query_interpretation': 'disjoint grids within trained transform families',
    'development_interpretation': 'only already exposed b1948b0a measured by either pilot; other3 cases explicitly unmeasured; not untouched validation',
    'program_policy': 'one native generation then all-demo bounded-VM verification before query',
    'repair_attempts': 0, 'confirmation_tasks': 0, 'demo_only_ttt': False,
    'public_solving_admitted': False, 'public_scoring_admitted': False,
    'four_l4_admitted': False, 'fp8_admitted': False, 'gate_threshold_changed': False,
}

def require(ok, message):
    if not ok: raise ValueError(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()+b'\n'

def digest(value): return hashlib.sha256(canonical(value)).hexdigest()

def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''): h.update(b)
    return h.hexdigest()

def checked_json(path, expected, *, cap=1024**2):
    path=Path(path).absolute()
    require(not any(p.is_symlink() for p in (path,*path.parents)), 'symlink input denied')
    require(path.is_file() and 0<path.stat().st_size<=cap, 'bounded regular JSON required')
    require(file_sha(path)==expected, 'immutable input digest differs')
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'duplicate JSON key');result[k]=v
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=lambda _:require(False,'nonfinite JSON'))

def validate_config(config):
    require(type(config) is dict,'probe configuration object required')
    allowed={'enabled','tiny_cpu','tokenizer_path','tiny_hidden_size','development_panel_path','development_panel_sha256',
             'training_root','model','started_epoch','maximum_seconds','test_checkpoint_updates','test_skip_ladder','test_failure','test_decoder_mode'}
    require(not set(config)-allowed,'unknown probe fields; public/confirmation inputs forbidden')
    require(config.get('enabled') is True,'explicit enabled=True required')
    tiny=config.get('tiny_cpu',False);require(type(tiny) is bool,'exact tiny_cpu Boolean required')
    duration=config.get('maximum_seconds',PROTOCOL['maximum_probe_seconds'])
    require(type(duration) is int and 30<=duration<=PROTOCOL['maximum_probe_seconds'],'bounded probe duration required')
    start=config.get('started_epoch')
    require(type(start) in (int,float) and math.isfinite(start) and start>0,'real pre-dispatch epoch required')
    if not tiny:
        require(not any(k.startswith('test_') or k in ('tokenizer_path','tiny_hidden_size') for k in config),'CPU fixture options forbidden in production')
        model_config=config.get('model',{})
        require(type(model_config) is dict,'model configuration object required')
        require(not any(k=='probe_fixture_generation_caps' or k.startswith('test_') for k in model_config),'nested CPU fixture options forbidden in production')
        require(duration==PROTOCOL['maximum_probe_seconds'],'production successor maximum is fixed at six hours')
    else:
        require(config.get('test_decoder_mode') in (None,'cached','full_prefix'),'unknown CPU decoder mode')
        require(config.get('test_skip_ladder',False) is False,'successor requires measured ladder even in CPU fixture')
        updates=config.get('test_checkpoint_updates',[1,2])
        require(type(updates) is list and updates==sorted(set(updates)) and 1<=len(updates)<=3 and all(type(x) is int and 1<=x<=PROTOCOL['maximum_updates_per_branch'] for x in updates),'bounded CPU checkpoint sequence required')
        require(type(config.get('test_skip_ladder',False)) is bool,'exact CPU ladder switch required')
        require(config.get('test_failure') in (None,'before_load','after_load','before_train','output'), 'unknown fault boundary')
    return deepcopy(config)
