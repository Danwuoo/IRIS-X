"""Training-only efficacy monitoring and rollback over physical metered work.

No public challenge, evaluator path or answer is accepted by this module.
Logical checkpoint restoration never restores the external physical ledger.
"""
from __future__ import annotations

import time
from pathlib import Path

from .budget import atomic_json, digest
from .effectiveness import evaluate_panel
from .stability import canary_decision


def _rows(report):
    return [{'sample_id': row['sample_id'],
             'valid': row['scoring_receipt_complete'],
             'nll_sum': (row['score'] or {}).get('nll_sum'),
             'token_count': (row['score'] or {}).get('token_count')}
            for row in report['rows']]


def _rank(report):
    return (-report['dev']['exact'], -report['learnability_controls']['exact'],
            -report['shape_correct'], -report['valid_grid'],
            report['mean_nll'] if report['mean_nll'] is not None else float('inf'))


def _saved_report(root, name, value):
    path = root / (name + '.json')
    atomic_json(path, value, exclusive=True)
    return {'path': path.name, 'sha256': digest(value), 'complete': value['complete'],
            'exact': value['exact'], 'shape_correct': value['shape_correct'],
            'valid_grid': value['valid_grid'], 'denominator': value['denominator'],
            'mean_nll': value['mean_nll'], 'gate_pass': value['gate_pass']}


def train_with_canaries(model, trainer, records, panel, manifest, *, deadline,
                        output, max_microbatches=4096, chunk_microbatches=128,
                        patience=2, max_loss_ratio=1.05, max_new_tokens=1024):
    """Real bounded SFT with base/early/best/final snapshots and efficacy evidence.

    The caller supplies a MeteredModel and MeteredTrainer in production. Base is
    truly pre-SFT. Each canary uses the exact same frozen panel, greedy decoding
    and completion budget. A missing comparison or nonfinite/failed training
    boundary prevents further training. A finite loss regression stops after
    the predeclared patience and restores the full best logical training state.
    """
    for name, value, upper in (('max_microbatches', max_microbatches, 4096),
                               ('chunk_microbatches', chunk_microbatches, 128),
                               ('patience', patience, 4)):
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError('invalid bounded ' + name)
    if not trainer.config.get('stability_mode'):
        raise ValueError('explicit stable training configuration required')
    root = Path(output); root.mkdir(parents=True, exist_ok=False)
    base = trainer.snapshot('base-pre-SFT')
    full_best = trainer.snapshot_training_state('base-pre-SFT-full')
    snapshots = {'base': base}
    reports, history, train_receipts = [], [], []
    initial = evaluate_panel(model, panel, deadline, manifest=manifest,
                             max_new_tokens=max_new_tokens)
    reports.append(_saved_report(root, 'canary-base', initial))
    best = initial
    snapshots['best'] = base
    attempted, optimizer_steps, bad = 0, 0, 0
    failed_receipts = []
    stopped = 'microbatch_cap'
    if not initial['complete']:
        stopped = 'base_canary_incomplete'
    try:
        while initial['complete'] and attempted < max_microbatches:
            if time.monotonic() >= deadline:
                stopped = 'stage_deadline'; break
            allowance = min(chunk_microbatches, max_microbatches - attempted)
            try:
                # Large optimizer states use the exporter's existing separate-
                # artifact namespace; they must not enter the evidence ZIP.
                receipt = trainer.train(records, max_steps=allowance, deadline=deadline,
                                        checkpoint_dir=root.parent / 'checkpoints' / 'stable-global')
            except Exception as exc:
                # Physical reservations were finalized/retained by the meter.
                stopped = 'training_failure:' + type(exc).__name__
                failed = getattr(exc, 'receipt', None)
                if isinstance(failed, dict):
                    path = root / ('failed-training-%05d.json' % attempted)
                    atomic_json(path, failed, exclusive=True)
                    failed_receipts.append({'path': path.name, 'sha256': digest(failed)})
                    attempted += failed.get('attempted_microbatches', 0)
                    optimizer_steps += failed.get('optimizer_steps', 0)
                history.append({'error': str(exc)[:512], 'new_work_stopped': True})
                break
            physical = receipt.get('attempted_microbatches', 0)
            if type(physical) is not int or not 0 < physical <= allowance:
                stopped = 'no_known_training_progress'; break
            attempted += physical
            optimizer_steps += receipt.get('optimizer_steps', 0)
            path = root / ('training-%05d.json' % attempted)
            atomic_json(path, receipt, exclusive=True)
            train_receipts.append({'path': path.name, 'sha256': digest(receipt),
                                   'attempted_microbatches': physical,
                                   'optimizer_steps': receipt.get('optimizer_steps', 0),
                                   'status': receipt['status']})
            current = trainer.snapshot('after-%d-microbatches' % attempted)
            if 'early' not in snapshots:
                snapshots['early'] = current
            previous_final = snapshots.get('final')
            snapshots['final'] = current
            if previous_final and previous_final not in (snapshots.get('early'), snapshots.get('best')):
                trainer.release_snapshot(previous_final)
            candidate = evaluate_panel(model, panel, deadline, manifest=manifest,
                                       max_new_tokens=max_new_tokens)
            reports.append(_saved_report(root, 'canary-%05d' % attempted, candidate))
            decision = canary_decision(_rows(best), _rows(candidate),
                expected_ids=[row['sample_id'] for row in initial['rows']],
                comparison_complete=best['complete'] and candidate['complete'],
                max_loss_ratio=max_loss_ratio)
            # Autoregressive regression is a distinct observed failure, not
            # silently hidden by improved teacher-forced likelihood.
            exact_regression = (candidate['dev']['exact'] < best['dev']['exact'] or
                candidate['learnability_controls']['exact'] < best['learnability_controls']['exact'])
            stable = decision['stable'] and not exact_regression
            bad = 0 if stable else bad + 1
            promoted = stable and _rank(candidate) < _rank(best)
            history.append({'microbatches': attempted, 'optimizer_steps': optimizer_steps,
                            'loss_decision': decision, 'autoregressive_exact_regression': exact_regression,
                            'consecutive_regressions': bad, 'promoted': promoted})
            if promoted:
                old_full = full_best
                full_best = trainer.snapshot_training_state('best-after-%d' % attempted)
                trainer.release_training_state(old_full)
                old_best = snapshots['best']; snapshots['best'] = current
                if old_best not in (base, snapshots.get('early'), snapshots.get('final')):
                    trainer.release_snapshot(old_best)
                best = candidate
            if not candidate['complete']:
                stopped = 'canary_incomplete'; break
            if bad >= patience:
                stopped = 'canary_regression'; break
            if receipt['status'] != 'complete':
                stopped = 'training_' + receipt['status']; break
    finally:
        restored = trainer.restore_training_state(full_best)
        trainer.release_training_state(full_best)
    # Missing early/final checkpoints are explicit aliases, never independent
    # training claims. A failure before a complete update still restores base.
    aliases = {}
    for name in ('early', 'final'):
        if name not in snapshots:
            snapshots[name] = base; aliases[name] = 'base-no-complete-training-boundary'
    report = {'format': 'irisx/stable-learning-cycle-v1', 'panel_sha256': panel['panel_sha256'],
              'attempted_microbatches': attempted, 'optimizer_steps': optimizer_steps,
              'maximum_microbatches': max_microbatches, 'chunk_microbatches': chunk_microbatches,
              'patience': patience, 'max_loss_ratio': max_loss_ratio,
              'status': stopped, 'canaries': reports, 'history': history,
              'stop_all_new_neural_work': (stopped.startswith('training_failure:') or
                  stopped in ('no_known_training_progress', 'base_canary_incomplete', 'canary_incomplete') or
                  stopped.startswith('training_failed')),
              'training_receipts': train_receipts, 'checkpoint_aliases': aliases,
              'failed_training_receipts': failed_receipts,
              'counter_scope': 'known returned receipts; external ledger remains authoritative for unknown work',
              'restored_best_complete_state': restored, 'physical_ledger_refunded': False,
              'public_answers_used': False}
    atomic_json(root / 'stable-learning-report.json', report, exclusive=True)
    return snapshots, report
