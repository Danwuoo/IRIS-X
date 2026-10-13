"""Reproduce consumed run007 source/candidate from portable authentic inputs.

This CPU build has no authentication, Provider, runtime, clock or dispatch path.
It preserves historical proof bytes and requires exact run007 input bindings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys


TOOL_REL = Path('tools/arc_qwen_rlvr004_20261013')
PINS = {
    'run005/candidate/ASSEMBLY-INVENTORY.json': 'de68ffa281990b844e41ea41d11357b2214a973048cd8e14ae64cab39159a5a0',
    'run006/candidate/ASSEMBLY-INVENTORY.json': '85a270c4fcacbe99c012b860fcd25f6b9d909df7c1aa17075c462a68c892277a',
    'run007/candidate/ASSEMBLY-INVENTORY.json': 'de519816720ceb3bf07e0bf015c888b7e4bd9fdb344c2dbe355281230920ee88',
    'run005/target-free-solver.json': '4c13f788cabe2213002593991cffcc15ffdcd6c04167967cbb9d2532536b5f47',
    'run006/reviews/installer-review.json': 'a1f10c8597cb11ff1f48c4b8cfdcb4d6ddd279e167b61bc2f1dc22d40d9c83b0',
    'run007/sealed-inputs/LIVE-IDENTITY.json': 'e0237cf5a14a018a06c74fa209547b974a20656f8d2b50576114d1b3cab1ea92',
    'run007/sealed-inputs/ORIGINAL-STATE-INVENTORY.json': '786e0adcbd6d6e1b1c8980cae63f5d2525299d98d136baf0f1f0cb6e8250e441',
    'run007/sealed-inputs/RUN006-STATE-INVENTORY.json': '4add439a6cfa036fe372c79489ebed714e2be7301afdc2812ccff795bdbf814a',
    'run007/sealed-inputs/observation/OBSERVATION.json': '1a231edcf368aa08b6e8620640261de0e55a6fd8fa1f5c79e9ab2a9ecb7cfd76',
    'run007/source-proposal-v2/PROPOSAL-INVENTORY.json': 'fbe2a8aed267c8e189c7a5dae17a6dd7e4625383f5403ad14c382ddb3ab44714',
    'run007/reviews/cudnn-runtime-review-v2.json': '70aa06ca28bf1dd9cef0eec2881f8ae58a58706d70345f455d94cfac6e68c5e4',
    'run007/reviews/cudnn-consumer-review-v2.json': 'deab3b4eb3f359db6ae7a764eaa0daa266fb6ff93d2f5a16a41f2a1b99098c39',
    'run007/reviews/solver-namespace-review.json': '718e3b49862d18f2b572942794f498f3aab48fbfa44f74a2475e4c7f28b66289',
    'run007/reviews/run007-final-runtime-review.json': '9deb61fccc77aed0d860382f5fff9d60994e12df0f151fe5d184ec7463d067d1',
    'run007/reviews/run007-final-material-review.json': 'f482bc61e783ecd29b7a57b1695646ba968eb3f7ca49f52428f63ad2e321df7e',
    'run007/OWNER-REQUEST.json': 'c82aeac9507ae63003f48493362c75d3926a2f1740acdd0a9df815103298ef14',
    'run007/candidate-proposal/SUCCESSOR-PROPOSAL.json': '2cad0b7e6aa56634e30f96e8e2642ea60f1c1844f01436548b2f8c74d029237b',
}
OVERLAYS = {
    'installer_logging_repair/bootstrap.py': '20aca4d463da2cec7dd0128dab1582cc009931666139f75f87fbbec9d1ba35b4',
    'cudnn_mapping_repair/environment_v2.py': '3d958c3707d14967977278b81581c57626eedd6ac9614384941cc70c058aa9e6',
    'cudnn_mapping_repair/release_checks.py': '3ec319ee3f0196ed94e5a20ec2d04554279c9ed0ebef1dab629c413b9d067dde',
    'publication_run007/rl_collect.py': '679c0d4f0995c8fa9063ff3098485001d9cf8980f93db1770f6b44104d25014a',
}
BUILDERS = {
    'preparation_successor/local_prepare_run007.py': '1456ee33a3ff89b81a543cd5a7a6ebbe1154f261c10912ba8e03184c39acd840',
    'preparation_successor/local_assemble_run007.py': '09e0d731536ff1b346be0e3430b78f3df1ec4517ffbd4c4769f73f3760e605e6',
}


class RebuildError(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise RebuildError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'explicit absolute path required')
    for ancestor in reversed((path, *path.parents)):
        try:
            info = ancestor.lstat()
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'link/reparse path denied')
    return path


def validate_paths(repository_root, inputs_root, output_root):
    repo, inputs, output = map(ordinary, (repository_root, inputs_root, output_root))
    need(repo.is_dir() and inputs.is_dir(), 'repository and authentic inputs must exist')
    need(output.is_relative_to(repo / '.irisx') and output != repo / '.irisx',
         'fresh output must be below repository/.irisx')
    need(not output.exists(), 'existing output denied; preserve earlier attempts')
    need(not output.is_relative_to(inputs) and not inputs.is_relative_to(output),
         'input/output overlap denied')
    need(os.name == 'posix', 'POSIX Python required; use real-home WSL or Linux')
    need(sys.version_info[:2] == (3, 12), 'Python 3.12 required for this historical rebuild')
    return repo, inputs, output


def read(path, limit=64 * 1024**2):
    path = ordinary(path)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
         'bounded single-link regular file required: ' + path.name)
    need(path.name.casefold() not in ('credentials.json', 'kaggle.json'), 'credential input denied')
    raw = path.read_bytes()
    need(len(raw) == info.st_size, 'input changed during read')
    return raw


def pinned(path, sha):
    raw = read(path)
    need(digest(raw) == sha, 'authentic input hash differs: ' + path.name)
    return raw


def relative(name):
    need(type(name) is str and bool(name), 'inventory path required')
    path = PurePosixPath(name)
    need(not path.is_absolute() and path.as_posix() == name
         and not any(part in ('..', '.') or ':' in part or '\\' in part for part in path.parts),
         'unsafe inventory path')
    return name


def closed_tree(root, inventory, inventory_name=None):
    root = ordinary(root)
    expected = set(inventory)
    if inventory_name:
        expected.add(inventory_name)
    actual = set()
    for path in root.rglob('*'):
        ordinary(path)
        if path.is_dir():
            continue
        actual.add(path.relative_to(root).as_posix())
    need(actual == expected, 'closed file set differs: ' + root.name)
    result = {}
    for name in sorted(expected):
        relative(name)
        raw = read(root / name)
        row = {'bytes': len(raw), 'sha256': digest(raw)}
        if name != inventory_name:
            need(inventory[name] == row, 'inventory bytes differ: ' + name)
        result[name] = row
    return result


def compare_tree(actual_root, expected_map):
    measured = closed_tree(actual_root, expected_map)
    need(measured == expected_map, 'reconstructed bytes differ')
    return {'files': len(measured), 'bytes': sum(row['bytes'] for row in measured.values()),
            'all_files_byte_identical': True}


def rebuild(*, repository_root, inputs_root, output_root):
    repo, inputs, output = validate_paths(repository_root, inputs_root, output_root)
    for name, sha in PINS.items():
        pinned(inputs / name, sha)
    for name, sha in {**OVERLAYS, **BUILDERS}.items():
        pinned(repo / TOOL_REL / name, sha)
    expected_candidates = {}
    for run in ('run005', 'run006', 'run007'):
        candidate = inputs / run / 'candidate'
        inventory = json.loads(read(candidate / 'ASSEMBLY-INVENTORY.json'))
        expected_candidates[run] = closed_tree(candidate, inventory, 'ASSEMBLY-INVENTORY.json')
    source_expected = closed_tree(inputs / 'run007/source-proposal-v2',
        json.loads(read(inputs / 'run007/source-proposal-v2/PROPOSAL-INVENTORY.json')),
        'PROPOSAL-INVENTORY.json')
    for run, name in (('run005', 'ORIGINAL-STATE-INVENTORY.json'),
                      ('run006', 'RUN006-STATE-INVENTORY.json')):
        closed_tree(inputs / run / 'state013',
                    json.loads(read(inputs / 'run007/sealed-inputs' / name)))

    # Import only pure source preparation/assembly; no operator or runtime entry.
    sys.path.insert(0, str(repo))
    from tools.arc_qwen_rlvr004_20261013.preparation_successor import local_prepare_run007 as p
    from tools.arc_qwen_rlvr004_20261013.preparation_successor import local_assemble_run007 as a
    need(Path(p.__file__).absolute() == repo / TOOL_REL / 'preparation_successor/local_prepare_run007.py'
         and Path(a.__file__).absolute() == repo / TOOL_REL / 'preparation_successor/local_assemble_run007.py',
         'cached builder from a different repository denied')

    source_output, candidate_output = output / 'source-rebuild', output / 'candidate-rebuild'
    source = p.prepare(repository_root=repo,
        identity_path=inputs / 'run007/sealed-inputs/LIVE-IDENTITY.json', output_root=source_output,
        solver_path=inputs / 'run005/target-free-solver.json',
        installer_overlay_path=repo / TOOL_REL / 'installer_logging_repair/bootstrap.py',
        installer_overlay_sha=OVERLAYS['installer_logging_repair/bootstrap.py'],
        installer_review_path=inputs / 'run006/reviews/installer-review.json',
        installer_review_sha=PINS['run006/reviews/installer-review.json'],
        cudnn_overlay_path=repo / TOOL_REL / 'cudnn_mapping_repair/environment_v2.py',
        cudnn_overlay_sha=OVERLAYS['cudnn_mapping_repair/environment_v2.py'],
        cudnn_review_path=inputs / 'run007/reviews/cudnn-runtime-review-v2.json',
        cudnn_review_sha=PINS['run007/reviews/cudnn-runtime-review-v2.json'],
        consumer_overlay_path=repo / TOOL_REL / 'cudnn_mapping_repair/release_checks.py',
        consumer_overlay_sha=OVERLAYS['cudnn_mapping_repair/release_checks.py'],
        consumer_review_path=inputs / 'run007/reviews/cudnn-consumer-review-v2.json',
        consumer_review_sha=PINS['run007/reviews/cudnn-consumer-review-v2.json'])
    source_comparison = compare_tree(source_output, source_expected)
    a.assemble(repository_root=repo, base_root=inputs / 'run005/candidate',
        source_proposal_root=source_output,
        source_proposal_inventory_sha=PINS['run007/source-proposal-v2/PROPOSAL-INVENTORY.json'],
        observation_root=inputs / 'run007/sealed-inputs/observation',
        observation_sha=PINS['run007/sealed-inputs/observation/OBSERVATION.json'],
        stop_attestation_path=inputs / 'run007/OWNER-REQUEST.json',
        stop_attestation_sha=PINS['run007/OWNER-REQUEST.json'],
        solver_path=inputs / 'run005/target-free-solver.json',
        new_solver_path=source_output / 'review-only/solver-descriptor.json',
        solver_review_path=inputs / 'run007/reviews/solver-namespace-review.json',
        solver_review_sha=PINS['run007/reviews/solver-namespace-review.json'],
        collector_path=repo / TOOL_REL / 'publication_run007/rl_collect.py',
        collector_sha=OVERLAYS['publication_run007/rl_collect.py'],
        output_root=candidate_output, mode='final',
        v35_state_root=inputs / 'run005/state013',
        v35_state_inventory_path=inputs / 'run007/sealed-inputs/ORIGINAL-STATE-INVENTORY.json',
        v35_state_inventory_sha=PINS['run007/sealed-inputs/ORIGINAL-STATE-INVENTORY.json'],
        run006_candidate_root=inputs / 'run006/candidate',
        run006_state_root=inputs / 'run006/state013',
        run006_state_inventory_path=inputs / 'run007/sealed-inputs/RUN006-STATE-INVENTORY.json',
        run006_state_inventory_sha=PINS['run007/sealed-inputs/RUN006-STATE-INVENTORY.json'],
        proposal_path=inputs / 'run007/candidate-proposal/SUCCESSOR-PROPOSAL.json',
        proposal_sha=PINS['run007/candidate-proposal/SUCCESSOR-PROPOSAL.json'],
        runtime_review_path=inputs / 'run007/reviews/run007-final-runtime-review.json',
        runtime_review_sha=PINS['run007/reviews/run007-final-runtime-review.json'],
        material_review_path=inputs / 'run007/reviews/run007-final-material-review.json',
        material_review_sha=PINS['run007/reviews/run007-final-material-review.json'])
    candidate_comparison = compare_tree(candidate_output, expected_candidates['run007'])
    report = {'format': 'irisx/run007-portable-consumed-build-v1', 'status': 'PASS',
        'source_comparison': source_comparison, 'candidate_comparison': candidate_comparison,
        'runtime_source_sha256': source['source_sha256'],
        'runtime_archive_sha256': source['source_archive_sha256'],
        'input_pins': PINS, 'overlay_pins': OVERLAYS, 'builder_pins': BUILDERS,
        'provider_calls': 0, 'model_or_GPU_calls': 0, 'credential_values_read': False,
        'historical_proof_bytes_rewritten': False,
        'answer_or_grid_content_semantically_parsed': False,
        'archive_member_reads': 'integrity hashing/CRC only through unchanged validators; no semantic parsing or solver/prompt exposure',
        'new_epoch_or_activation_created': False, 'publication_authorized_by_rebuild': False,
        'consumed_run_identity': {'code_version': 20, 'notebook_version': 39,
                                  'epoch': 1791908053, 'deadline': 1791951253},
        'scope': 'CPU reproduction of already consumed run007; no GPU or scientific success claim.'}
    with (output / 'REBUILD-REPORT.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', required=True, type=Path)
    parser.add_argument('--inputs-root', required=True, type=Path)
    parser.add_argument('--output-root', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = rebuild(**vars(args))
    except (RebuildError, OSError, ValueError, RuntimeError) as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error), 'provider_calls': 0}), file=sys.stderr)
        return 1
    print(json.dumps({'status': result['status'], 'source_comparison': result['source_comparison'],
                      'candidate_comparison': result['candidate_comparison'], 'provider_calls': 0}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
