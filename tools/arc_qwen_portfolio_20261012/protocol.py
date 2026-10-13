"""Closed, preregistered manual portfolio experiment contract."""
from copy import deepcopy
import math
from tools.arc_qwen_probe_20261012.protocol import require, canonical, digest, file_sha, checked_json

PROTOCOL = {
    'format': 'irisx/qwen14b-portfolio-protocol-v1',
    'model': 'Qwen/Qwen3-14B', 'revision': '40c069824f4251a91eefaf281ebe4c544efd3e18',
    'precision': 'bf16-base-fp32-lora', 'rank': 8, 'alpha': 16,
    'context_limit': 2048, 'prompt_cap': 1792, 'grid_output_cap': 256, 'program_output_cap': 256,
    'batch_size': 1, 'seed': 1917, 'maximum_seconds': 43200, 'maximum_session_seconds': 43200,
    'maximum_load_seconds': 1800, 'length_ladder': [128,512,2048],
    'checkpoint_updates': [8,16], 'maximum_updates_per_branch': 16,
    'branches': ['grid_lora','program_lora'], 'learning_rate': .0002,
    'warmup_updates': 4, 'schedule_updates': 32,
    'maximum_completion_tokens_per_branch': 32768, 'maximum_input_tokens_per_branch_training': 32768,
    'denominators': {'seen_regression':13,'same_family_query':12,'heldout_family':6,'canary':8,'real_arc_holdout':24},
    'program_candidate_order':['base','program8','program16'], 'maximum_answers':2,
    'selection':'all demonstrations fit; valid query; fixed candidate order; top two distinct grids; explicit abstention',
    'canary_selector':'branch aligned; complete eight-case coverage; earlier update final tie; all candidates retained',
    'scoring_boundary':'all holdout candidate predictions and choices sealed before target escrow scoring',
    'real_arc_training_stage_enabled':False,
    'real_arc_interpretation':'fixed official training-source development parents; no public evaluation tasks or public score',
    'regression_interpretation':'old13 already inspected; output cap256 changes previous64/128 configuration',
    'cache_scope':'unchanged bounded empirical synthetic128/512/2048 controls; no universal equivalence claim',
    'fallback':'no full-prefix science if cache is inadmissible; preserve diagnostics and reason',
    'checkpoint_store_maximum_bytes':2*1024**3, 'checkpoint_shard_maximum_bytes':32*1024**2,
    'checkpoint_assets_separate_from_evidence_archive':True,
    'terminal_statuses':['PORTFOLIO_COMPLETE','PORTFOLIO_PARTIAL','PORTFOLIO_DIAGNOSTICS_ONLY','PORTFOLIO_FAILED'],
    'public_score':None,'public_solving_admitted':False,'fp8_admitted':False,'four_l4_admitted':False,
}

def validate_config(config):
    require(type(config) is dict,'configuration object required')
    allowed={'enabled','tiny_cpu','tokenizer_path','tiny_hidden_size','development_panel_path','development_panel_sha256',
             'training_root','model','started_epoch','maximum_seconds','test_failure','test_fixture_dataset'}
    require(not set(config)-allowed,'unknown configuration field')
    require(config.get('enabled') is True,'explicit enable required')
    tiny=config.get('tiny_cpu',False);require(type(tiny) is bool,'exact tiny Boolean required')
    start=config.get('started_epoch');require(type(start) in (int,float) and math.isfinite(start) and start>0,'finite actual start epoch required')
    seconds=config.get('maximum_seconds',43200)
    require(type(seconds) is int and 120<=seconds<=43200,'session duration must not exceed12h')
    if not tiny:
        require(seconds==43200,'production maximum fixed at12h')
        require(not any(k.startswith('test_') or k in ('tokenizer_path','tiny_hidden_size','development_panel_path','development_panel_sha256') for k in config),'fixture fields denied in production')
        m=config.get('model');require(type(m) is dict,'production model configuration required')
        require(not any(k.startswith('test_') or k in ('tiny_cpu','probe_fixture_generation_caps') for k in m),'nested fixture fields denied')
        require(type(config.get('training_root')) is str,'pinned training root required')
    else:
        require(config.get('test_failure') in (None,'before_load','after_load','before_train','output'),'unknown test fault')
        require(config.get('test_fixture_dataset',False) is True,'explicit synthetic panel required for CPU fixture')
    return deepcopy(config)
