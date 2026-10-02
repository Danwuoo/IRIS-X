"""Exactly bound first global-256 source batch, logical and physical layouts."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.arc_nvarc_gpu_preflight_v2 import CORPUS_SHA
from irisx.arc_nvarc_packing import pack_sequences
from irisx.arc_nvarc_qwen3_packing import execution_slices
from irisx.canonical import digest_value
from irisx.errors import ValidationError


def profile(output,ceiling=32768):
    prefix=ROOT/'.irisx/nvarc-original/materials/source-shuffle-prefix-20261002-001'
    proof=json.loads((prefix/'verification.json').read_bytes())
    samples=json.loads((prefix/'samples.json').read_bytes())
    if (output.exists() or proof['corpus_manifest_sha256']!=CORPUS_SHA or proof['cursor']!=512 or
            proof['samples_sha256']!='82d5e1f60f7d8a2748d9aa4011e7cd5478106405f06089b6cea7b9085b9521e6' or
            sha_file(prefix/'samples.json')!=proof['samples_sha256'] or digest_value(samples)!=proof['sample_digest'] or
            len(samples)!=512 or [r['shuffle_position'] for r in samples]!=list(range(512))):
        raise ValidationError('new identity and exact unfiltered source prefix required')
    batch=samples[:256];rank_profiles=[];exposure=Counter();sources=Counter()
    for row in batch:
        if not isinstance(row.get('source_id'),str) or not isinstance(row.get('exposure_tags'),list):
            raise ValidationError('original source and exposure metadata required')
        exposure.update(row['exposure_tags']);sources.update([row['source_id']])
    for rank in range(4):
        rows=batch[rank::4];logical=pack_sequences(rows)
        physical=[piece for pack in logical for piece in execution_slices(pack,ceiling)]
        indices=[segment['row_index'] for piece in physical for segment in piece['segments']]
        if sorted(indices)!=list(range(64)):raise ValidationError('whole rank sequence coverage differs')
        rank_profiles.append({'rank':rank,'whole_sequences':64,'logical_pack_count':len(logical),
            'logical_padded_tokens':[len(pack['input_ids']) for pack in logical],
            'logical_pack_digests':[digest_value(pack) for pack in logical],
            'physical_forward_count':len(physical),'physical_input_tokens':[p['input_tokens'] for p in physical],
            'physical_supervised_tokens':[p['supervised_tokens'] for p in physical],
            'physical_pack_digests':[digest_value(p) for p in physical],
            'logical_to_physical_segments':[p['execution_slice'] for p in physical]})
    report={'format':'irisx/nvarc-source-physical-packing-profile-v1','owner_decision':'Decision 0054',
        'run_id':output.name,'source_prefix_sha256':proof['samples_sha256'],
        'source_verification_sha256':sha_file(prefix/'verification.json'),'source_stream_identity':proof['source_stream_identity'],
        'global_batch_size':256,'shuffle_start':0,'shuffle_stop':256,'data_digest':digest_value(batch),
        'global_input_tokens':sum(len(r['input_ids']) for r in batch),
        'global_supervised_tokens':sum(sum(v>=0 for v in r['labels'][1:]) for r in batch),
        'maximum_whole_sequence_tokens':max(len(r['input_ids']) for r in batch),
        'packing_capacity':256000,'length_multiple':64,'maximum_physical_input_tokens':ceiling,
        'source_counts':dict(sources),'exposure_counts':dict(exposure),'ranks':rank_profiles,
        'collective_slots_per_rank':max(r['physical_forward_count'] for r in rank_profiles),
        'dummy_forward_counts':[max(r['physical_forward_count'] for r in rank_profiles)-r['physical_forward_count'] for r in rank_profiles],
        'truncated_records':0,'filtered_records':0,'optimizer_steps':0,'model_calls':0,'maximum_paid_usd':0,
        'gpu_memory_verified':False,'training_throughput_verified':False,'original_nemo_parallelism_parity':False}
    output.mkdir(parents=True);atomic(output/'profile.json',report)
    return {key:report[key] for key in ('run_id','global_input_tokens','global_supervised_tokens',
        'maximum_whole_sequence_tokens','collective_slots_per_rank','dummy_forward_counts')}|{
        'logical_packs':[r['logical_pack_count'] for r in rank_profiles],
        'physical_forwards':[r['physical_forward_count'] for r in rank_profiles],
        'profile_sha256':sha_file(output/'profile.json')}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(profile(args.output)))
