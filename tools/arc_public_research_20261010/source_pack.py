"""Reproducible source-only Dataset; public task data is a separate asset."""
from __future__ import annotations
import argparse, hashlib, json, stat, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = 'f25a7cd4765de9fe815273bcd6060804324c183b'
CODE_REFERENCE = 'danielwuu/iris-x-public120-code-20261010/1'
DATA_REFERENCE = 'danielwuu/iris-x-public120-data-20261010/1'

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def regular(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('regular unlinked source required')
    return path.read_bytes()

def collect_sources(root=ROOT):
    from tools.arc_public_research_20261010.public_evaluator import SCORER_PINS
    paths = set(SCORER_PINS)
    paths |= {'tools/arc_next_models.py','tools/arc_next_index_repair.py'}
    for name in ('arc_consolidated_20261010','arc_public_research_20261010'):
        package = root / 'tools' / name
        paths.update(p.relative_to(root).as_posix() for p in package.glob('*.py')
                     if p.name not in {'build_notebook.py','source_pack.py'})
        paths.update(p.relative_to(root).as_posix() for p in (package/'legacy').glob('*.py'))
        paths.update(p.relative_to(root).as_posix() for p in (package/'data').glob('*.json'))
    if 'tools/arc_public_research_20261010/runner.py' not in paths:
        raise ValueError('new runner required')
    result = {name:regular(root/name) for name in sorted(paths)}
    if sum(map(len,result.values())) > 16*1024**2 or len(result)>512:
        raise ValueError('source package ceiling')
    if any(sha(result[k]) != value for k,value in SCORER_PINS.items()):
        raise ValueError('historical scorer changed')
    return result

def write_new(path, raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw)

def build_code(output, root=ROOT):
    output = Path(output)
    if output.exists():raise ValueError('fresh code build directory required')
    source = collect_sources(root); output.mkdir(parents=True)
    archive = output/'source.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name, raw in source.items():
            info=zipfile.ZipInfo(name,(2026,10,10,0,0,0));info.external_attr=(stat.S_IFREG|0o644)<<16
            info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
    manifest={'format':'irisx/public120-code-material-v1','reference':CODE_REFERENCE,'base_commit':BASE_COMMIT,
        'source_identity':{name:sha(raw) for name,raw in source.items()},
        'files':{name:{'sha256':sha(raw),'bytes':len(raw)} for name,raw in source.items()},
        'archive':{'name':'source.zip','sha256':sha(archive.read_bytes()),'bytes':archive.stat().st_size},
        'contains_model_weights':False,'contains_public_test_answers':False,'execution':'manual research; no automatic model or GPU run'}
    write_new(output/'manifest.json',canonical(manifest)+b'\n')
    write_new(output/'NOTICE.txt',b'Private owner project source. Existing repository notices remain in their original files. No license grant for the complete private project is implied. Public ARC task data is distributed separately with its original Apache-2.0 license.\n')
    return {'reference':CODE_REFERENCE,'manifest_sha256':sha((output/'manifest.json').read_bytes()),'archive':manifest['archive'],'files':len(source)}

def build_data_manifest(data_root):
    data_root=Path(data_root)
    files={p.relative_to(data_root).as_posix():{'sha256':sha(regular(p)),'bytes':p.stat().st_size}
           for p in sorted(data_root.rglob('*')) if p.is_file()}
    if any(not name.startswith(('solver/','evaluator/')) for name in files):raise ValueError('only two data roles admitted')
    roles={role:sha(regular(data_root/role/'manifest.json')) for role in ('solver','evaluator')}
    manifest={'format':'irisx/public120-data-material-v1','reference':DATA_REFERENCE,'files':files,
              'role_manifests':roles,'tasks':120,'tests':167,'purpose':'public-development research, no untouched holdout claim',
              'repository':'https://github.com/arcprize/ARC-AGI-2.git','commit':'f3283f727488ad98fe575ea6a5ac981e4a188e49','license':'Apache-2.0'}
    write_new(data_root/'public-data-material.json',canonical(manifest)+b'\n')
    return {'reference':DATA_REFERENCE,'manifest_sha256':sha((data_root/'public-data-material.json').read_bytes()),'role_manifests':roles,'files':len(files)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--code-output',required=True);parser.add_argument('--data-root',required=True)
    args=parser.parse_args();print(json.dumps({'code':build_code(args.code_output),'data':build_data_manifest(args.data_root)},sort_keys=True))
