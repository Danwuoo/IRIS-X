"""Reconstruct exact runtime/source artifacts offline; no Git, provider or model calls.

The isolated runtime is assembled only through the pinned closed path mapping.
Exact release metadata is copied from the tracked freeze. Both archives are rebuilt
with the original deterministic ZIP settings. Default mode explicitly omits raw predecessor evidence and does not claim a complete historical release. Full release requires --full-release and an exact hash-verified external predecessor archive. Neither mode activates a notebook.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import zipfile
import runtime_assembly as a

INVENTORY_SHA256 = 'ea5119a7cbf45dc091ede5aa79f4d213c7b41ca5302e461168d027184b2f1766'
SOURCE_ZIP_SHA256 = '99014aba72618c01675ce464c0a3c595ab624568a6c3be11b6a0f28298c85113'
DEPLOYMENT = 'tools/arc_qwen_checkpoint_repair_deployment_20261012'


def zip_files(path, files):
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(files.items()):
            item = zipfile.ZipInfo(a.safe_name(name), (2026, 10, 12, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (stat.S_IFREG | 0o644) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(item, raw)


EXTERNAL_MEMBER = "predecessor/evidence.zip"


def reproduce(repository_root, output_root, *, full_release=False, predecessor_evidence=None):
    repo, out = a._check_locations(repository_root, output_root)
    deployment = repo / DEPLOYMENT
    release = deployment / 'release/transfer003'
    inventory = a.read_document(release / 'ASSEMBLY-INVENTORY.json', INVENTORY_SHA256)
    a.need(type(full_release) is bool, 'exact_reconstruction_mode_required')
    external = None
    a.need(predecessor_evidence is None or full_release, 'external_input_requires_explicit_full_release')
    if full_release:
        a.need(predecessor_evidence is not None, 'external_predecessor_evidence_required')
        path = a.explicit_path(predecessor_evidence)
        row = inventory[EXTERNAL_MEMBER]
        with a.directory(path.parent) as fd:
            external = a.read_regular(fd, path.name, row['bytes'])
        a.need(len(external) == row['bytes'] and a.sha(external) == row['sha256'], 'external_predecessor_evidence_mismatch')
    metadata = {}
    with a.directory(release) as fd:
        for name, row in inventory.items():
            a.need(name == a.safe_name(row['path']), 'release_inventory_path')
            if name.endswith('.zip'):
                continue
            raw = a.read_regular(fd, name, a.DOCUMENT_CAP)
            a.need(len(raw) == row['bytes'] and a.sha(raw) == row['sha256'], 'release_metadata_mismatch')
            metadata[name] = raw
        metadata['ASSEMBLY-INVENTORY.json'] = a.read_regular(fd, 'ASSEMBLY-INVENTORY.json', a.DOCUMENT_CAP)
    with a.directory(out.parent) as fd:
        a._require_absent(fd, out.name)
        os.mkdir(out.name, 0o700, dir_fd=fd)
    runtime = out / 'runtime'
    assembled = a.assemble_runtime(repository_root=repo, output_root=runtime,
        source_freeze=release / 'SOURCE-FREEZE.json', publication_manifest=release / 'publication-manifest.json',
        path_map=deployment / 'runtime-path-map.json')
    entries, inner = a.load_contract(source_freeze=release / 'SOURCE-FREEZE.json',
        publication_manifest=release / 'publication-manifest.json', path_map=deployment / 'runtime-path-map.json')
    with a.directory(runtime) as fd:
        a._verify_tree(fd, entries, inner)
        sources = {n: a.read_regular(fd, n, a.FILE_CAP, require_mode=True) for n in entries}
    target = out / ('release' if full_release else 'release-source-only')
    target.mkdir()
    for name, raw in metadata.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
        path.chmod(0o644)
    zip_files(target / 'code-payload/source.zip', sources)
    a.need(a.sha((target / 'code-payload/source.zip').read_bytes()) == SOURCE_ZIP_SHA256, 'source_zip_not_exact')
    zip_files(target / 'code-dataset-upload.zip',
              {p.name: p.read_bytes() for p in (target / 'code-payload').iterdir()})
    if full_release:
        (target / EXTERNAL_MEMBER).write_bytes(external)
        (target / EXTERNAL_MEMBER).chmod(0o644)
    expected_names = set(inventory) - (set() if full_release else {EXTERNAL_MEMBER})
    for name in sorted(expected_names):
        row = inventory[name]
        raw = (target / name).read_bytes()
        a.need(len(raw) == row['bytes'] and a.sha(raw) == row['sha256'], 'reproduced_release_not_exact')
    a.need({p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} ==
           expected_names | {'ASSEMBLY-INVENTORY.json'}, 'reproduced_release_not_closed')
    return {'status': 'PASS' if full_release else 'SOURCE_ONLY_RECONSTRUCTION_PASS',
            'complete_historical_release': full_release, 'release_files': len(expected_names) + 1,
            'expected_full_release_files': len(inventory) + 1,
            'omitted_external_evidence': [] if full_release else [inventory[EXTERNAL_MEMBER]],
            'runtime_members': assembled['runtime_member_count'], 'source_zip_sha256': SOURCE_ZIP_SHA256,
            'source_identity_sha256': a.FULL_IDENTITY_SHA256, 'provider_or_model_calls': 0,
            'runtime': str(runtime), 'release': str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--full-release', action='store_true', help='Explicit complete historical release, requiring external predecessor evidence')
    parser.add_argument('--predecessor-evidence', type=Path)
    args = parser.parse_args()
    print(json.dumps(reproduce(args.repository_root, args.output_root, full_release=args.full_release, predecessor_evidence=args.predecessor_evidence), sort_keys=True))


if __name__ == '__main__':
    main()
