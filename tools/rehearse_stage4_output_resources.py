"""Bounded synthetic CPU large-evidence E01 export/recovery measurement.

Measures the real eager generation/projection implementation with synthetic JSON.
It does not run native transcript replay, a model, GPU, official input or scoring.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import resource
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json, validate_submission
from tools.nvarc_native_multitask import canonical, digest, require, write
from tools.nvarc_output_lifecycle import GenerationStore, outcomes


def disk_bytes(root):
    return sum(path.stat().st_size for path in Path(root).rglob('*') if path.is_file())


def run(root, *, evidence_bytes=64*1024**2, maximum_seconds=180):
    root = Path(root)
    require(not root.exists() and type(evidence_bytes) is int and 1024 <= evidence_bytes <= 256*1024**2 and
        type(maximum_seconds) is int and 10 <= maximum_seconds <= 600, 'new bounded synthetic rehearsal required')
    root.mkdir(parents=True)
    challenges = {'renamed-a': {'train': [{'input': [[1]], 'output': [[2]]}],
        'test': [{'input': [[3]]}, {'input': [[4]]}]},
        'different-b': {'train': [{'input': [[2]], 'output': [[1]]}], 'test': [{'input': [[5]]}]}}
    submission = {key: [{'attempt_1': [[0]], 'attempt_2': [[0]]} for _ in task['test']]
                  for key, task in challenges.items()}
    counts = validate_submission(challenges, submission)
    evidence = {'synthetic': True, 'chunks': ['x'*65536]*(evidence_bytes//65536),
                'tail': 'x'*(evidence_bytes%65536), 'native_qualification': False}
    values = {'native-evidence.json': evidence, 'submission-audit.json': {'synthetic': True, 'model_candidates': 0},
        'submission.json': submission, 'export-process.json': {'synthetic': True, 'new_model_calls': 0},
        'official-summary.json': {'run_id': 'stage4-synthetic-resource-001', 'strict_same_runtime_export_completed': False}}
    bindings = {'run_id': 'stage4-synthetic-resource-001', 'challenges_digest': digest(challenges),
                'fixture_digest': digest(values)}
    timings = {}; started = time.monotonic(); deadline = started+maximum_seconds
    sample = {'disk_peak_bytes': 0}; stop = threading.Event()
    def monitor():
        while not stop.wait(.02): sample['disk_peak_bytes'] = max(sample['disk_peak_bytes'], disk_bytes(root))
    thread = threading.Thread(target=monitor, daemon=True); thread.start()
    store = GenerationStore(root/'working', 'official', bindings, deadline=deadline)
    original_evidence = len(canonical(evidence))
    try:
        begin = time.monotonic(); store.publish(values, evidence_qualified=False)
        timings['eager_publication_readback_projection_seconds'] = time.monotonic()-begin
        store.verify_projection(); manifest, bodies = store.read()
        submission_sha = hashlib.sha256(bodies['submission.json']).hexdigest()
        # Retain the same immutable generation; damage only a replaceable root
        # projection, simulating a stopped post-commit producer interruption.
        (store.root/'submission.json').write_bytes(b'{')
        begin = time.monotonic()
        def revalidate(found, previous):
            require(found['bindings'] == bindings and previous == values and
                    found['outcomes']['evidence_qualified'] is False, 'synthetic exact recovery differs')
            validate_submission(challenges, previous['submission.json'])
        store.recover(revalidate); store.verify_projection()
        timings['semantic_synthetic_revalidation_recovery_seconds'] = time.monotonic()-begin
        recovered, recovered_bodies = store.read()
        require(recovered['generation'] == manifest['generation'] and
            hashlib.sha256(recovered_bodies['submission.json']).hexdigest() == submission_sha,
            'committed exact-generation recovery differs')
    finally:
        stop.set(); thread.join(timeout=2)
        sample['disk_peak_bytes'] = max(sample['disk_peak_bytes'], disk_bytes(root))
    result = {'format': 'irisx/stage4-synthetic-output-resource-v1',
        'synthetic_requested_evidence_payload_bytes': evidence_bytes, 'synthetic_native_evidence_json_bytes': original_evidence,
        'historical_native_evidence_reference_bytes': 661320886, 'historical_reference_scale_attested': False,
        'observed_process_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'observed_disk_peak_sampled_bytes': sample['disk_peak_bytes'], 'disk_sampling_interval_seconds': .02,
        'disk_peak_measurement': 'sampled process-visible files; filesystem allocation/block peak not attested',
        'wall_seconds': time.monotonic()-started, 'maximum_seconds': maximum_seconds, 'timings': timings,
        'gpu_memory_highwater_bytes': None, 'gpu_runs': 0, 'new_model_calls': 0, 'external_calls': 0,
        'counts': counts, 'same_committed_generation_recovered': True,
        'submission_sha256': submission_sha,
        'boundaries': ['synthetic JSON only', 'not strict native transcript export', 'not full input/GPU scale',
            'not power-loss durability', 'not official scoring readiness'],
        **outcomes(True, 'success', False)}
    write(root/'resource-receipt.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--evidence-mib', type=int, default=64); parser.add_argument('--maximum-seconds', type=int, default=180)
    args = parser.parse_args(); print(canonical(run(args.root, evidence_bytes=args.evidence_mib*1024**2,
        maximum_seconds=args.maximum_seconds)).decode())


if __name__ == '__main__': main()
