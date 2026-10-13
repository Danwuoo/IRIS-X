"""Reconstruct the exact frozen release offline; no Git, provider or model calls.

The isolated runtime is assembled only through the pinned closed path mapping.
Exact release metadata is copied from the tracked freeze. Both archives are rebuilt
with the original deterministic ZIP settings. This does not activate a notebook.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import zipfile
import runtime_assembly as a

INVENTORY_SHA256 = '338d4f92c7382f3c784e42d636e6d8d5cc37406615bb552ea359c612936fabe6'
SOURCE_ZIP_SHA256 = '6fe28472f84860b58895eed066169560e4d5fa62b6114594f7794a2924e2206c'
DEPLOYMENT = 'tools/arc_qwen_transfer_repair_deployment_20261012'


def zip_files(path, files):
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(files.items()):
            item = zipfile.ZipInfo(a.safe_name(name), (2026, 10, 12, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (stat.S_IFREG | 0o644) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(item, raw)


def reproduce(repository_root, output_root):
    repo, out = a._check_locations(repository_root, output_root)
    deployment = repo / DEPLOYMENT
    release = deployment / 'release/transfer002'
    inventory = a.read_document(release / 'ASSEMBLY-INVENTORY.json', INVENTORY_SHA256)
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
    target = out / 'release'
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
    for name, row in inventory.items():
        raw = (target / name).read_bytes()
        a.need(len(raw) == row['bytes'] and a.sha(raw) == row['sha256'], 'reproduced_release_not_exact')
    a.need({p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} ==
           set(inventory) | {'ASSEMBLY-INVENTORY.json'}, 'reproduced_release_not_closed')
    return {'status': 'PASS', 'release_files': len(inventory) + 1,
            'runtime_members': assembled['runtime_member_count'], 'source_zip_sha256': SOURCE_ZIP_SHA256,
            'source_identity_sha256': a.FULL_IDENTITY_SHA256, 'provider_or_model_calls': 0,
            'runtime': str(runtime), 'release': str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reproduce(args.repository_root, args.output_root), sort_keys=True))


if __name__ == '__main__':
    main()
