"""Explicit offline official-model capacity comparison worker; no remote actions."""
from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import math
from pathlib import Path
import time

from tools.arc2_goal_sprint_20261017.launch import (
    require, sha, write_new, verify_inventory, TRAINING_MANIFEST_SHA256, SOLVER_MANIFEST_SHA256,
)
from .controller import verify_source



def run_public_bundle(engine_factory, public, comparison, *, output, deadline, config):
    """Freeze verified dev choice, then run every post-SFT arm without selection."""
    from .public import run_public_diagnostic, write_unexecuted_public
    from .controller import TREATMENTS
    from tools.arc2_goal_sprint_20261017.run import atomic_json
    from tools.arc2_goal_sprint_20261017.data import digest
    output = Path(output)
    binding = json.loads((output / 'comparison/source-binding.json').read_bytes())
    require(binding['split']['receipt']['public_digest'] == digest(public),
            'PUBLIC payload differs from original answer-free source binding')
    require(comparison['complete'] is True, 'PUBLIC cannot start after incomplete development comparison')
    require(json.loads((output / 'comparison/report.json').read_bytes()) == comparison,
            'PUBLIC must bind actual persisted comparison report')
    frozen = {'comparison_complete': True, 'comparison_report_sha256': sha(output / 'comparison/report.json'),
        'protocol_sha256': comparison['protocol_sha256'], 'source_identity': comparison['source_identity'],
        'selected_treatment': comparison['selected_treatment'], 'selection_frozen_before_public': True,
        'public_config': config}
    write_new(output / 'frozen-selection.json', frozen)
    report = {'format': 'irisx/nvarc-capacity-public-bundle-v1', 'frozen_selection': frozen,
        'requested_treatments': list(TREATMENTS), 'treatments': {}, 'complete': False,
        'loading': {}, 'public_scoring_performed': False, 'no_ttt': True,
        'full_requested_queries_per_treatment': 167}
    atomic_json(output / 'public-bundle.json', report)
    blocked = None
    for treatment in TREATMENTS:
        checkpoint = comparison['treatments'][treatment]['checkpoint']
        pin = {k: checkpoint[k] for k in ('root', 'manifest_sha256', 'state_sha256')}
        kwargs = {'solver_payload': public, 'frozen_selection': frozen, 'checkpoint_pin': pin,
            'output_dir': output / 'public' / treatment, 'treatment': treatment, 'deadline': deadline, 'config': config}
        if blocked or time.time() >= deadline:
            report['treatments'][treatment] = write_unexecuted_public(**kwargs,
                reason=blocked or 'global deadline before model load')
            report['loading'][treatment] = {'attempted': False, 'wall_seconds': 0.0}
        else:
            engine = None; loading_started = time.monotonic()
            try:
                engine = engine_factory(treatment)
                engine.load_checkpoint({k: pin[k] for k in ('root', 'manifest_sha256')})
                report['loading'][treatment] = {'attempted': True, 'complete': True,
                    'wall_seconds': time.monotonic() - loading_started}
                report['treatments'][treatment] = run_public_diagnostic(engine, **kwargs)
            except Exception as error:
                blocked = 'model/checkpoint admission failed; no later model dispatch: ' + type(error).__name__
                report['loading'][treatment] = {'attempted': True, 'complete': False,
                    'wall_seconds': time.monotonic() - loading_started, 'error': type(error).__name__,
                    'failed_load_device_work_unknown': True}
                if not (kwargs['output_dir'] / 'report.json').exists():
                    report['treatments'][treatment] = write_unexecuted_public(**kwargs, reason=blocked)
                else:
                    report['treatments'][treatment] = json.loads((kwargs['output_dir'] / 'report.json').read_bytes())
            finally:
                cuda = engine is not None and engine.device.type == 'cuda'
                engine = None; gc.collect()
                if cuda:
                    import torch
                    torch.cuda.empty_cache()
        atomic_json(output / 'public-bundle.json', report)
    report['complete'] = all(v['complete'] for v in report['treatments'].values())
    atomic_json(output / 'public-bundle.json', report)
    require(sha(output / 'comparison/report.json') == frozen['comparison_report_sha256'],
            'PUBLIC diagnostic changed frozen development selection')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('model-root', 'training-root', 'training-manifest', 'public-challenges', 'output', 'source-root', 'source-manifest'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--started-epoch', type=float, required=True)
    parser.add_argument('--session-deadline-epoch', type=float, required=True)
    parser.add_argument('--deadline-epoch', type=float, required=True)
    parser.add_argument('--comparison-deadline-epoch', type=float, required=True)
    parser.add_argument('--public-diagnostics', action='store_true')
    parser.add_argument('--execute-official', action='store_true')
    args = parser.parse_args(argv)
    require(args.execute_official, 'explicit --execute-official required')
    now = time.time()
    require(all(math.isfinite(v) for v in (args.started_epoch, args.session_deadline_epoch, args.deadline_epoch, args.comparison_deadline_epoch))
            and 0 < args.started_epoch <= now < args.comparison_deadline_epoch <= min(args.deadline_epoch, now + 7200)
            and args.deadline_epoch <= args.session_deadline_epoch == args.started_epoch + 43200,
            'original12h session and at-most7200s comparison deadline required')
    snapshot = json.loads(args.source_manifest.read_bytes())
    verify_source(args.source_root, snapshot, args.source_sha256)
    import torch
    from tools.arc2_goal_sprint_20261017.data import load_data
    from tools.nvarc_posttrain_20261017.materials import verify_model
    from .model import load_engine
    from .workflow import prepare_panels, run_workflow, DEFAULT_CONFIG, TREATMENTS
    require(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'one actual available CUDA device required')
    free, total = torch.cuda.mem_get_info(0)
    require(free >= 40 * 1024**3, 'conservative40GiB free-memory envelope unavailable; capacity peak remains unmeasured')
    require(not args.output.exists(), 'new immutable worker output root required')
    args.output.mkdir(parents=True)
    # Official exact file digests, tensor inventory and BF16 source are checked
    # before any model object loads. ReArc and unmanifested materials are denied.
    identity = verify_model(args.model_root, '2b')
    verify_inventory(args.public_challenges.parent, SOLVER_MANIFEST_SHA256)
    train, dev, public, split = load_data(args.training_root, args.training_manifest, args.public_challenges,
                                        expected_manifest_sha256=TRAINING_MANIFEST_SHA256)
    prepared = prepare_panels(train, dev, public, split, training_root=args.training_root,
                              training_manifest_path=args.training_manifest)
    write_new(args.output / 'admission.json', {'source_identity': args.source_sha256,
        'model_identity': identity, 'training_manifest_sha256': TRAINING_MANIFEST_SHA256,
        'solver_manifest_sha256': SOLVER_MANIFEST_SHA256, 'public_answer_free': True,
        'cuda': {'device_count': 1, 'name': torch.cuda.get_device_name(0), 'free_bytes_before_load': free,
                 'total_bytes': total, 'free_memory_envelope_measured_feasibility_claimed': False},
        'runtime': {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'peft', 'safetensors')},
        'official_model_checked_before_load': True, 'ReArc_model_admitted': False})
    def factory(treatment):
        engine = load_engine(args.model_root, treatment=treatment, device='cuda',
            seed=DEFAULT_CONFIG['seed'], adapter_seed=DEFAULT_CONFIG['adapter_seed'])
        require(engine.base_identity == identity, 'fresh engine official model identity differs')
        return engine
    if args.public_diagnostics:
        write_new(args.output / 'public-plan.json', {'treatments': list(TREATMENTS),
            'public_config': {k: DEFAULT_CONFIG[k] for k in ('context_tokens', 'generation_tokens', 'evaluation_seed', 'views', 'ttt_steps')},
            'full_requested_tasks': 120, 'full_requested_queries_per_treatment': 167,
            'phase_deadline_epoch': args.deadline_epoch, 'selection_uses_public': False,
            'plan_frozen_before_comparison': True})
    report = run_workflow(factory, prepared, deadline=args.comparison_deadline_epoch,
        output=args.output / 'comparison', source_identity=args.source_sha256)
    public_report = None
    if args.public_diagnostics and report['complete']:
        cfg = {k: DEFAULT_CONFIG[k] for k in ('context_tokens', 'generation_tokens', 'evaluation_seed', 'views', 'ttt_steps')}
        public_report = run_public_bundle(factory, public, report, output=args.output,
                                          deadline=args.deadline_epoch, config=cfg)
    verify_source(args.source_root, snapshot, args.source_sha256)
    result = {'format': 'irisx/nvarc-capacity-worker-v1', 'comparison_complete': report['complete'],
        'selected_treatment': report['selected_treatment'], 'source_identity': args.source_sha256,
        'public_diagnostics_requested': args.public_diagnostics,
        'public_diagnostics_complete': None if public_report is None else public_report['complete'],
        'public_scoring_performed': False, 'completed_before_deadline': time.time() < args.deadline_epoch}
    write_new(args.output / 'result.json', result)
    print(json.dumps(result, sort_keys=True))
    return 0 if report['complete'] and result['completed_before_deadline'] and (not args.public_diagnostics or (public_report and public_report['complete'])) else 2


if __name__ == '__main__':
    raise SystemExit(main())
