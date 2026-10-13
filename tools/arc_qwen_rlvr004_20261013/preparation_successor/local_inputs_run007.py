"""Seal authentic v35/v37 state and official current readbacks. No provider I/O.

Measuring an inventory never manufactures a provider receipt or closure. The
separate final assembly replays both original dispatch chains before admission.
"""
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).absolute().parents[3]))
from tools.arc_qwen_rlvr004_20261013.preparation_successor import local_assemble_run007 as a


def seal(*, repository_root, state_root, run006_state_root, observation_root, output_root):
    repo, state, run006, observation, output = map(a.p.ordinary,
        (repository_root, state_root, run006_state_root, observation_root, output_root))
    a.need(output.is_relative_to(repo / '.irisx') and output != repo / '.irisx' and not output.exists(),
           'fresh ignored input seal required')
    for source in (state, run006, observation):
        a.need(not output.is_relative_to(source) and not source.is_relative_to(output), 'input/output overlap')
    old_helper = a.p.load_module(a.pinned(a.HERE / 'v35_lineage.py', a.LINEAGE_HELPER_SHA),
        'run007_seal_v35', a.HERE / 'v35_lineage.py')
    new_helper = a.p.load_module(a.pinned(a.HERE / 'run006_lineage.py', a.RUN006_LINEAGE_SHA),
        'run007_seal_v37', a.HERE / 'run006_lineage.py')
    selected = {name: a.p.desc(a.read(state / name)) for name in old_helper.STATE_NAMES}
    run006_selected = {name: a.p.desc(a.read(run006 / name)) for name in new_helper.STATE_NAMES}
    original_raw = a.read(observation / 'OBSERVATION.json')
    original = a.obj(original_raw)
    a.need(original['format'] == 'irisx/run006-live-predecessor-observation-v1', 'original official packet schema')
    a.need(original['code_version'] == 19 and original['notebook_version'] == 37
           and original['provider_status'] == 'ERROR' and original['gpu_unavailable_stop'] is False
           and original['saved_source_sha256'] == new_helper.SAVED_SHA, 'exact failed run006 source identity')
    files = a.closed_files(observation, original['closed_files'], extra=('OBSERVATION.json',))
    names = {'saved_source': 'saved_source.ipynb', 'notebook_before': 'metadata-before.json',
        'notebook_after': 'metadata-after.json', 'notebook_status': 'status.json',
        'dataset_before': 'dataset-before.json', 'dataset_after': 'dataset-after.json'}
    a.need(set(files) == set(names.values()), 'six authentic official response bodies required')
    files['provider-observation.json'] = original_raw
    evidence = {role: a.descriptor(files[name], name) for role, name in names.items()}
    evidence['original_observation'] = a.descriptor(original_raw, 'provider-observation.json')
    document = {**original, 'format': 'irisx/run007-local-current-predecessor-observation-v1',
        'closed_files': {name: a.p.desc(body) for name, body in sorted(files.items())}, 'evidence': evidence,
        'original_epoch': new_helper.EPOCH, 'original_deadline': new_helper.DEADLINE,
        'source_observation_sha256': a.sha(original_raw), 'provider_calls_by_sealer': 0,
        'local_reconstruction': True, 'scope': 'Actual retained official terminal packet; not runtime/scoring/physical-cost proof.'}
    versions = {'code_predecessor': original['code_version'], 'code': original['code_version'] + 1,
        'notebook_predecessor': original['notebook_version'], 'inactive': original['notebook_version'] + 1,
        'active': original['notebook_version'] + 2}
    identity = {'format': 'irisx/preparation-successor-proposed-identity-v1',
        'status': 'PROPOSED_NOT_PROVIDER_RESERVED', 'run_id': 'irisx-qwen14b-rlvr-20261013-run007', 'versions': versions}
    a.p.identity(a.encoded(identity))
    blobs = {'ORIGINAL-STATE-INVENTORY.json': a.encoded(selected),
        'RUN006-STATE-INVENTORY.json': a.encoded(run006_selected), 'LIVE-IDENTITY.json': a.encoded(identity),
        'observation/OBSERVATION.json': a.encoded(document), **{'observation/' + name: body for name, body in files.items()}}
    a.write_output(output, blobs)
    a.observation_inputs(output / 'observation', a.sha(blobs['observation/OBSERVATION.json']))
    return {'format': 'irisx/run007-local-input-seal-v1', 'status': 'INPUTS_MEASURED_DISPATCH_REPLAY_REQUIRED',
        'original_state_inventory_sha256': a.sha(blobs['ORIGINAL-STATE-INVENTORY.json']),
        'run006_state_inventory_sha256': a.sha(blobs['RUN006-STATE-INVENTORY.json']),
        'observation_sha256': a.sha(blobs['observation/OBSERVATION.json']),
        'identity_sha256': a.sha(blobs['LIVE-IDENTITY.json']), 'output_root': str(output),
        'provider_calls': 0, 'runtime_or_scientific_success': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'state-root', 'run006-state-root', 'observation-root', 'output-root'):
        parser.add_argument('--' + name, required=True)
    print(a.encoded(seal(**vars(parser.parse_args()))).decode(), end='')


if __name__ == '__main__':
    main()
