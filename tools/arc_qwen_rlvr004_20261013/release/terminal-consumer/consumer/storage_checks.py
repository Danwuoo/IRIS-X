"""Mandatory analytical storage/expansion artifacts, independently recomputed."""
from .safe_io import Root,need,same


def storage_contract(root,source_root):
    source=Root(source_root);cfg='baseline/materials/qwen14b/hf-overlay/config.json';c=source.json(cfg)
    rank=8;h=c['hidden_size'];k=c['num_key_value_heads']*c['head_dim'];q=c['num_attention_heads']*c['head_dim'];i=c['intermediate_size'];layers=c['num_hidden_layers']
    parameters=layers*rank*((h+q)+(h+k)+(h+k)+(q+h)+3*(h+i));fp32=parameters*4
    tensor=2*fp32+6*(4*fp32);metadata=7*32*1024**2
    expected={'format':'owned-rl-checkpoint-storage-v2','maximum_checkpoint_count':7,'config_sha256':source.file_sha(cfg),'rank':rank,
        'seven_projection_layers':layers,'lora_parameter_count':parameters,'parameter_dtype':'float32',
        'adapter_tensor_bytes':fp32,'base_payload_bytes':2*fp32,'trained_payload_bytes':4*fp32,
        'worst_case_checkpoint_tensor_bytes':tensor,'metadata_allowance_bytes':metadata,
        'estimated_checkpoint_upper_bytes':tensor+metadata,'checkpoint_store_cap_bytes':4*1024**3,
        'zip_temporary_cap_bytes':4*1024**3,'free_disk_reserve_bytes':4*1024**3,
        'full_store_plus_temporary_zip_plus_reserve_bytes':12*1024**3,
        'optimizer_moments':'two FP32 Adam tensors per adapter parameter; step scalars inside metadata allowance',
        'not_included':'frozen14B native weights remain external; never checkpoint-copied'}
    need(same(root.json('checkpoint-storage-plan.json'),expected),'mandatory source-owned seven-store analytical storage plan differs')
    audit=256*(1024*1024+256*1024+2*64*1024);journal=8192*400000;projections=2*8192*40000;remaining=512*1024**2
    expansion={'format':'owned-rl-evidence-expansion-v1','tokenizer_sha256':source.file_sha('baseline/materials/qwen14b/hf-overlay/tokenizer.json'),
        'grid_ascii_pieces':25,'EOS_choices':2,'maximum_step_support':27,'trajectories':256,
        'max_steps_per_trajectory':1024,'enforced_step_bytes':1024,'enforced_trajectory_metadata_bytes':256*1024,
        'per_replay_allowance_bytes':64*1024,'replay_projection_copies':2,'audit_upper_bytes':audit,
        'max_source_model_operations':(256+8192)*4+256*4+288+334+128,'enforced_event_count_cap':40000,
        'enforced_journal_record_bytes':8192,'enforced_journal_record_count':400000,'journal_upper_bytes':journal,
        'event_projection_copies_bound':2,'event_projection_upper_bytes':projections,
        'predictions_calibration_metadata_allowance_bytes':remaining,'derived_evidence_upper_bytes':audit+journal+projections+remaining,
        'evidence_cap_bytes':5*1024**3,'single_json_cap_bytes':2*1024**3,'largest_planned_audit_json_upper_bytes':audit//4,
        'checkpoint_cap_bytes':4*1024**3,'checkpoint_temporary_ZIP_cap_bytes':4*1024**3,
        'optional_full_export_ZIP_cap_bytes':13*1024**3+16*1024**2,
        'optional_full_export_contains_checkpoint_store_and_zip':True,'free_disk_reserve_bytes':4*1024**3,
        'unknown_work_retained':True,'silent_truncation':False}
    need(same(root.json('evidence-expansion-plan.json'),expansion),'mandatory complete audit/journal/evidence expansion plan differs')
    return {'checkpoint_analytical_bytes':tensor+metadata,'evidence_analytical_bytes':expansion['derived_evidence_upper_bytes'],
            'maximum_checkpoint_stores':7,'free_disk_reserve_bytes':4*1024**3}
