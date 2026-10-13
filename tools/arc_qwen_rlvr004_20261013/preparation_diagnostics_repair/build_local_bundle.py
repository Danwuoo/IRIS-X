"""Build an inert, exact run005-based CPU review bundle; never publish or run it.

The frozen source payload is reconstructed unchanged. Only the preparation and
launcher deployment overlays are substituted. This bundle contains no active
notebook, operator approval, authentication, model weights or evaluator data.
Its inherited run005 paths are reference coordinates, never a reusable session.
A separately reviewed fresh identity and fully bound release remain mandatory.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import types

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
REPO = TOOL.parents[1]
BASE_SOURCE_SHA256 = '4050616ed0ed34d19501be416650a09ae5cc9c86c875b349a056baec9308f3e3'
BASE_ARCHIVE_SHA256 = '22fc93ae1dfbc4d4a7c90cf9907668af5d697dece28cb9211dea82c776d7dc9e'
PARENT_OVERLAY_SHA256 = '0ccdeecc8398098c0240d919c8ff9f4f51e5455ee96debd35c8c7c8ce10bb24b'


def module(name, path):
    loaded = types.ModuleType(name)
    loaded.__file__ = str(path)
    loaded.__package__ = ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(loaded))
    return loaded


def build(output_root):
    assembler = module('development_reference_assembler', TOOL / 'prepare_successor_release.py')
    output = assembler.ordinary(output_root)
    assembler.need(output.is_relative_to(REPO / '.irisx') and output != REPO / '.irisx', 'ignored local review output required')
    assembler.need(not output.exists(), 'fresh local review output required')
    declared = assembler.obj(assembler.read(TOOL / 'release/notebook-release.json'))['deployment']
    base = {}
    for name in assembler.DEPLOYMENT_NAMES:
        raw = assembler.read(TOOL / 'support/deployment' / name)
        assembler.need({'bytes': len(raw), 'sha256': assembler.sha(raw)} == declared[name], 'frozen deployment differs')
        base['code-payload/deployment/' + name] = raw
    wrappers = assembler.read(TOOL / 'support/assembly/verify_parent_wrappers.py')
    wrapper_pin = assembler.obj(assembler.read(TOOL / 'release/publication-manifest.json'))['parent_wrapper_verifier']
    assembler.need({'bytes': len(wrappers), 'sha256': assembler.sha(wrappers)} ==
                   {key: wrapper_pin[key] for key in ('bytes', 'sha256')}, 'frozen wrapper verifier differs')
    base['assembly/verify_parent_wrappers.py'] = wrappers
    deployment, _ = assembler.derive_deployment(base)
    original_deployment = {name: {'bytes': len(raw), 'sha256': assembler.sha(raw)} for name, raw in deployment.items()}
    for name in ('launch_notebook.py', 'prepare_entry.py'):
        deployment[name] = assembler.read(HERE / name)
        compile(deployment[name], name, 'exec')
    # The paired local reference must agree; a source004 support copy is invalid.
    assembler.need(b'irisx-qwen14b-rlvr-20261012-environment005' in deployment['launch_notebook.py'] and
                   b'irisx-qwen14b-rlvr-20261012-run005' in deployment['notebook_builder.py'] and
                   b'irisx-qwen14b-rlvr-20261012-source005' in deployment['notebook_builder.py'], 'paired reference namespace differs')
    output.mkdir(parents=True)
    rebuilt = assembler.rebuild_source(repository_root=REPO,
        parent_overlay=TOOL / 'driver_path_repair/parent_scoring.py',
        parent_overlay_sha=PARENT_OVERLAY_SHA256, output_root=output / 'source-reference')
    assembler.need(rebuilt['source_sha256'] == BASE_SOURCE_SHA256 and
                   rebuilt['source_archive_sha256'] == BASE_ARCHIVE_SHA256, 'exact run005 source reference differs')
    (output / 'deployment').mkdir()
    for name, raw in deployment.items():
        with (output / 'deployment' / name).open('xb') as stream:
            stream.write(raw)
    # Preinstall authentication reads this environment companion, but there is
    # deliberately no material review, operator, finalized notebook, or approval.
    environment = assembler.read(output / 'source-reference/environment-run005.json')
    (output / 'source-reference/release').mkdir()
    with (output / 'source-reference/release/REVIEWED-ENVIRONMENT.json').open('xb') as stream:
        stream.write(environment)
    record = {'format': 'irisx/preparation-diagnostics-development-bundle-v1',
              'status': 'INERT_CPU_REVIEW_ONLY', 'production_admitted': False,
              'production_dispatch_authorized': False, 'publication_authorized_by_artifact': False,
              'source_sha256': BASE_SOURCE_SHA256, 'source_archive_sha256': BASE_ARCHIVE_SHA256,
              'source_members': 259, 'source_bytes_changed': False,
              'deployment_reference': 'frozen-code18-run005-never-reuse-session',
              'original_deployment': original_deployment,
              'deployment': {name: {'bytes': len(raw), 'sha256': assembler.sha(raw)} for name, raw in deployment.items()},
              'changed_deployment_members': ['launch_notebook.py', 'prepare_entry.py'],
              'active_notebook_included': False, 'material_review_included': False,
              'model_or_GPU_execution_claim': False, 'scoring_authority': False,
              'manual_failure_root_cause': 'UNVERIFIED_PENDING_ORIGINAL_INNER_LOGS'}
    with (output / 'DEVELOPMENT-BUNDLE.json').open('xb') as stream:
        stream.write(assembler.encoded(record))
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output_root), sort_keys=True))
