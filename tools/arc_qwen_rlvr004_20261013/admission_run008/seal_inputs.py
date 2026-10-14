"""Seal the publisher's exact official bracket; no new provider observations."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0, str(Path(__file__).absolute().parents[3]))
from tools.arc_qwen_rlvr004_20261013.admission_run008 import assemble as a


def seal(*, repository_root, observation_root, observation_sha, output_root):
    root = a.p.ordinary(observation_root)
    output = a.output_path(repository_root, output_root)
    a.need(not output.is_relative_to(root) and not root.is_relative_to(output), 'input/output overlap')
    raw = a.pinned(root / 'OBSERVATION.json', observation_sha)
    old = a.obj(raw)
    a.need(old.get('format') == 'irisx/run008-live-predecessor-observation-v1', 'actual publisher bracket schema')
    mapping = {'saved_source': ('saved_source.ipynb', 'saved_source_sha256'),
        'notebook_before': ('metadata-before.json', 'metadata_before_sha256'),
        'notebook_after': ('metadata-after.json', 'metadata_after_sha256'),
        'notebook_status': ('status.json', 'status_sha256'),
        'dataset_before': ('dataset.json', 'dataset_metadata_sha256'),
        'dataset_after': ('dataset-after.json', 'dataset_after_sha256')}
    a.need({p.name for p in root.iterdir()} == {'OBSERVATION.json'} | {row[0] for row in mapping.values()}, 'closed actual bracket')
    files = {name: a.pinned(root / name, old[key]) for name, key in mapping.values()}
    files['publisher-observation.json'] = raw
    evidence = {role: a.descriptor(files[name], name) for role, (name, _) in mapping.items()}
    evidence['original_observation'] = a.descriptor(raw, 'publisher-observation.json')
    observation = {**old, 'format': 'irisx/run008-native-current-predecessor-observation-v1',
        'closed_files': {name: a.desc(body) for name, body in sorted(files.items())}, 'evidence': evidence,
        'original_observation_sha256': observation_sha, 'provider_calls_by_sealer': 0,
        'scope': 'Exact existing official bracket; local sealing is not a new provider observation or runtime/scientific evidence.'}
    files['OBSERVATION.json'] = a.encoded(observation)
    a.s.write_output(output, files)
    try:
        a.observation_inputs(output, a.sha(files['OBSERVATION.json']))
    except BaseException:
        a.s.shutil.rmtree(output)
        raise
    return {'status': 'EXACT_OFFICIAL_INPUTS_SEALED', 'output_root': str(output),
        'observation_sha256': a.sha(files['OBSERVATION.json']), 'original_observation_sha256': observation_sha,
        'provider_calls': 0, 'runtime_or_scientific_success': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'observation-root', 'observation-sha', 'output-root'):
        parser.add_argument('--' + name, required=True)
    print(a.encoded(seal(**vars(parser.parse_args()))).decode(), end='')


if __name__ == '__main__': main()
