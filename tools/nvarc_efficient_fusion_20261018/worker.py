"""Explicit offline official2B fusion execution; no provider/network operations."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import math
from pathlib import Path
import time
from tools.arc2_goal_sprint_20261017.launch import (
    require, write_new, verify_inventory, TRAINING_MANIFEST_SHA256, SOLVER_MANIFEST_SHA256,
)
from .controller import verify_source


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('model-root', 'training-root', 'training-manifest', 'public-challenges', 'output', 'source-root', 'source-manifest'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    for key in ('started-epoch', 'session-deadline-epoch', 'deadline-epoch', 'training-deadline-epoch'):
        parser.add_argument('--'+key, type=float, required=True)
    parser.add_argument('--execute-official', action='store_true'); args = parser.parse_args(argv)
    now = time.time(); require(args.execute_official, 'explicit --execute-official required')
    require(all(math.isfinite(v) for v in (args.started_epoch, args.session_deadline_epoch, args.deadline_epoch, args.training_deadline_epoch))
        and 0 < args.started_epoch <= now < args.training_deadline_epoch < args.deadline_epoch <= min(now+10800, args.session_deadline_epoch)
        and args.session_deadline_epoch == args.started_epoch+43200,
        'original finite session and bounded active/training/evaluation deadlines required')
    snapshot = json.loads(args.source_manifest.read_bytes()); verify_source(args.source_root, snapshot, args.source_sha256)
    from tools.arc2_goal_sprint_20261017.data import load_data
    from tools.nvarc_posttrain_20261017.materials import verify_model
    from .panels import prepare_panels
    require(not args.output.exists(), 'new immutable worker destination required'); args.output.mkdir(parents=True)
    data_start = time.monotonic()
    verify_inventory(args.public_challenges.parent, SOLVER_MANIFEST_SHA256)
    data = load_data(args.training_root, args.training_manifest, args.public_challenges,
                     expected_manifest_sha256=TRAINING_MANIFEST_SHA256)
    prepared = prepare_panels(*data, training_root=args.training_root, training_manifest_path=args.training_manifest)
    # Freeze the complete larger panels before constructing or sampling a model.
    write_new(args.output/'frozen-panels.json', prepared)
    data_seconds = time.monotonic()-data_start
    model_start = time.monotonic(); identity = verify_model(args.model_root, '2b'); checksum_seconds = time.monotonic()-model_start
    import torch
    from tools.nvarc_posttrain_20261017.engine import CompactEngine
    from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
    from .contracts import DEFAULT_CONFIG
    from .workflow import run_workflow
    require(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'one actual available CUDA device required')
    free, total = torch.cuda.mem_get_info(0)
    require(free >= 40*1024**3 and total*4//5 >= 40*1024**3,
            'conservative40GiB free within80percent allocator envelope required; feasibility remains unmeasured')
    torch.cuda.set_per_process_memory_fraction(.8, 0); torch.set_num_threads(1)
    write_new(args.output/'admission.json', {'source_identity': args.source_sha256, 'model_identity': identity,
        'training_manifest_sha256': TRAINING_MANIFEST_SHA256, 'solver_manifest_sha256': SOLVER_MANIFEST_SHA256,
        'panel_pins': prepared['pins'], 'panel_and_source_admission_wall_seconds': data_seconds,
        'official_model_checksum_wall_seconds': checksum_seconds, 'model_loaded_before_panel_freeze': False,
        'cuda': {'device_count': 1, 'name': torch.cuda.get_device_name(0), 'free_bytes_before_load': free, 'total_bytes': total},
        'runtime': {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'peft', 'safetensors')},
        'ReArc_model_admitted': False, 'public_answers_used': False})
    load_start = time.monotonic()
    engine = CompactEngine.load(args.model_root, base_identity=identity, variant='2b', device='cuda',
        seed=DEFAULT_CONFIG['seed'], adapter_seed=DEFAULT_CONFIG['adapter_seed'], probability_policy=FP32_BACKBONE_POLICY)
    engine.sync()
    write_new(args.output/'model-loading.json', {'wall_seconds': time.monotonic()-load_start,
        'trainable_contract': engine.trainable_inventory, 'probability_execution': engine.probability_execution_receipt(),
        'peak_allocated_bytes': torch.cuda.max_memory_allocated(0), 'peak_reserved_bytes': torch.cuda.max_memory_reserved(0)})
    def audit(event, **fields): print(json.dumps({'event': event, **fields}, sort_keys=True), flush=True)
    report = run_workflow(engine, prepared, deadline=args.deadline_epoch, training_deadline=args.training_deadline_epoch,
        output=args.output/'comparison', source_identity=args.source_sha256, audit=audit)
    verify_source(args.source_root, snapshot, args.source_sha256)
    result = {'format': 'irisx/efficient-fusion-worker-v1', 'complete': report['complete'],
        'selected_arm': report['selected_arm'], 'source_identity': args.source_sha256,
        'public_scoring_performed': False, 'completed_before_deadline': time.time() < args.deadline_epoch}
    write_new(args.output/'result.json', result); print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result['complete'] and result['completed_before_deadline'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
