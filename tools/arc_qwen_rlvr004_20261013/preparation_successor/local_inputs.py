"""Seal authentic local input copies without credentials, archive inspection or provider calls.

This locally reconstructed helper measures original selected state bytes and
the official current-provider packet. It does not invent an original receipt,
grant runtime admission, read evaluator archive members, or sample a new clock.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).absolute().parents[3]))
from tools.arc_qwen_rlvr004_20261013.preparation_successor import local_assemble_run006 as a


def seal(*, repository_root, state_root, observation_root, output_root):
    repo, state, observation, output = map(a.p.ordinary, (repository_root, state_root, observation_root, output_root))
    a.need(output.is_relative_to(repo / '.irisx') and not output.exists(), 'fresh ignored local input seal required')
    for source in (state, observation):
        a.need(not output.is_relative_to(source) and not source.is_relative_to(output), 'sealed input/output overlap')
    lineage = a.p.load_module(a.pinned(a.HERE / 'v35_lineage.py', a.LINEAGE_HELPER_SHA), 'input_seal_original_lineage', a.HERE / 'v35_lineage.py')
    selected = {name: a.p.desc(a.read(state / name)) for name in lineage.STATE_NAMES}
    original_raw = a.read(observation / 'OBSERVATION.json')
    original = a.obj(original_raw)
    a.need(original['format'] == 'irisx/run006-live-predecessor-observation-v1', 'official local observation format')
    files = a.closed_files(observation, original['closed_files'], extra=('OBSERVATION.json',))
    names = {'saved_source': 'saved_source.ipynb', 'notebook_before': 'metadata-before.json',
             'notebook_after': 'metadata-after.json', 'notebook_status': 'status.json',
             'dataset_before': 'dataset-before.json', 'dataset_after': 'dataset-after.json'}
    a.need(set(files) == set(names.values()), 'exact six official observation bodies')
    files['provider-observation.json'] = original_raw
    evidence = {role: a.descriptor(files[name], name) for role, name in names.items()}
    evidence['original_observation'] = a.descriptor(original_raw, 'provider-observation.json')
    document = {**original, 'format': 'irisx/run006-local-current-predecessor-observation-v1',
        'closed_files': {name: a.p.desc(raw) for name, raw in sorted(files.items())}, 'evidence': evidence,
        'original_epoch': a.p.OLD_EPOCH, 'original_deadline': a.p.OLD_DEADLINE,
        'source_observation_sha256': a.sha(original_raw), 'provider_calls_by_sealer': 0,
        'local_reconstruction': True, 'scope': 'Exact retained official read-only packet; no runtime or scientific success.'}
    versions = {'code_predecessor': original['code_version'], 'code': original['code_version'] + 1,
        'notebook_predecessor': original['notebook_version'], 'inactive': original['notebook_version'] + 1,
        'active': original['notebook_version'] + 2}
    identity = {'format': 'irisx/preparation-successor-proposed-identity-v1',
        'status': 'PROPOSED_NOT_PROVIDER_RESERVED', 'run_id': 'irisx-qwen14b-rlvr-20261013-run006', 'versions': versions}
    a.p.identity(a.encoded(identity))
    blobs = {'ORIGINAL-STATE-INVENTORY.json': a.encoded(selected), 'LIVE-IDENTITY.json': a.encoded(identity),
        'observation/OBSERVATION.json': a.encoded(document),
        **{'observation/' + name: raw for name, raw in files.items()}}
    a.write_output(output, blobs)
    # This verifies all selected state against original provider receipt chains;
    # the freshly measured inventory alone never makes a historical proof.
    return {'format': 'irisx/run006-local-input-seal-v1', 'status': 'INPUTS_MEASURED_CHAIN_VERIFICATION_REQUIRED',
        'original_state_inventory_sha256': a.sha(blobs['ORIGINAL-STATE-INVENTORY.json']),
        'observation_sha256': a.sha(blobs['observation/OBSERVATION.json']),
        'identity_sha256': a.sha(blobs['LIVE-IDENTITY.json']), 'output_root': str(output),
        'provider_calls': 0, 'runtime_success': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'state-root', 'observation-root', 'output-root'):
        parser.add_argument('--' + name, required=True)
    print(a.encoded(seal(**vars(parser.parse_args()))).decode(), end='')


if __name__ == '__main__':
    main()
