"""Stdlib-only exact code17 mount acceptance. No imports of model/runtime code."""
from __future__ import annotations
import hashlib, io, json, os, stat, zipfile
from pathlib import Path, PurePosixPath

MAX_SOURCE = 64 * 1024**2
MAX_MEMBERS = 1024
FORMAT = 'irisx/rlvr-code-material-v1'


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def safe_name(name):
    need(type(name) is str and name and '\\' not in name and ':' not in name and not any(ord(c)<32 for c in name), 'unsafe relative path')
    path = PurePosixPath(name)
    need(not path.is_absolute() and str(path)==name and all(p not in ('', '.', '..') for p in name.split('/')), 'unsafe relative path')
    return name


def clean_path(value):
    need(type(value) in (str, Path) or isinstance(value, Path), 'explicit path required')
    raw = os.fspath(value)
    need(raw.startswith('/') and str(Path(raw))==raw and '..' not in Path(raw).parts and '\\' not in raw and not any(ord(c)<32 for c in raw), 'canonical absolute path required')
    path = Path(raw)
    for item in (path, *path.parents):
        need(not item.is_symlink(), 'symlink path forbidden')
    return path


def read_regular(path, maximum=MAX_SOURCE):
    path=clean_path(path)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and 0<=before.st_size<=maximum, 'bounded regular file required')
        chunks=[]; total=0
        while True:
            block=os.read(fd,min(1024**2,maximum+1-total))
            if not block:break
            total+=len(block);need(total<=maximum,'file byte cap');chunks.append(block)
        after=os.fstat(fd)
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'file changed during read')
        current=path.stat(follow_symlinks=False)
        need((current.st_dev,current.st_ino)==(before.st_dev,before.st_ino) and total==before.st_size,'file replaced during read')
        return b''.join(chunks)
    finally:
        os.close(fd)


def zip_source(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(safe_name(name),(2026,10,12,0,0,0));info.create_system=3
            info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_STORED
            archive.writestr(info,raw)
    return stream.getvalue()


def _rows(rows):
    need(type(rows) is dict and 0<len(rows)<=MAX_MEMBERS,'bounded nonempty file inventory')
    for name,row in rows.items():
        safe_name(name)
        need(type(row) is dict and set(row)=={'bytes','sha256'} and type(row['bytes']) is int and 0<=row['bytes']<=16*1024**2,'closed file descriptor')
        need(type(row['sha256']) is str and len(row['sha256'])==64 and all(c in '0123456789abcdef' for c in row['sha256']),'SHA256 required')
    need(sum(row['bytes'] for row in rows.values())<=MAX_SOURCE,'source expansion cap')


def _actual_files(root):
    result=set()
    for directory,dirs,files in os.walk(root,followlinks=False):
        need(len(result)<=3*MAX_MEMBERS,'mount inventory cap')
        for name in dirs:
            path=Path(directory)/name
            need(not path.is_symlink() and path.is_dir(),'nonregular mount directory')
        for name in files:
            path=Path(directory)/name
            need(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode),'nonregular mount file')
            result.add(path.relative_to(root).as_posix())
    return result


def inspect_release(code_root, *, manifest_sha256, archive_sha256):
    code=clean_path(code_root);need(code.is_dir(),'code mount missing')
    raw=read_regular(code/'manifest.json',2*1024**2)
    need(digest(raw)==manifest_sha256,'code manifest hash differs')
    manifest=parse(raw)
    need(set(manifest)=={'format','reference','source','auxiliary_files'} and manifest['format']==FORMAT and manifest['reference']=='danielwuu/iris-x-learning-agent-code-20261011/17','exact code17 manifest required')
    source=manifest['source']
    need(type(source) is dict and set(source)=={'archive','source_sha256','files'},'closed source manifest')
    _rows(source['files']);_rows(manifest['auxiliary_files'])
    need(not set(source['files']) & set(manifest['auxiliary_files']),'producer and auxiliary file collision')
    arch=source['archive']
    need(type(arch) is dict and set(arch)=={'name','bytes','sha256'} and arch['name']=='source.zip' and arch['sha256']==archive_sha256 and type(arch['bytes']) is int and 0<arch['bytes']<=MAX_SOURCE,'source archive descriptor')
    need(digest(json.dumps(sorted((n,r['sha256']) for n,r in source['files'].items()),sort_keys=True,separators=(',',':'),allow_nan=False).encode())==source['source_sha256'],'full raw source inventory digest differs')
    observed=_actual_files(code);aux=set(manifest['auxiliary_files']);metadata={'manifest.json'}
    need(metadata<=observed,'code metadata absent')
    files={}
    if 'source.zip' in observed:
        need(observed==metadata|aux|{'source.zip'},'ambiguous archive/extracted/extra code files')
        archive_raw=read_regular(code/'source.zip')
        need(len(archive_raw)==arch['bytes'] and digest(archive_raw)==archive_sha256,'source archive bytes differ')
        with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
            members=archive.infolist()
            need(len(members)==len(source['files']) and len({m.filename for m in members})==len(members),'duplicate/missing source ZIP members')
            for member in members:
                name=safe_name(member.filename)
                need(name in source['files'] and not member.is_dir() and not member.flag_bits&1 and stat.S_IFMT(member.external_attr>>16) in (0,stat.S_IFREG),'unknown/nonregular source ZIP member')
                need(member.compress_type==zipfile.ZIP_STORED and member.file_size==source['files'][name]['bytes'],'exact stored source ZIP member')
                raw=archive.read(member);need(digest(raw)==source['files'][name]['sha256'],'source member digest differs')
                files[name]=raw
        need(zip_source(files)==archive_raw,'noncanonical source archive bytes')
        mode='verified-archive'
    else:
        layouts=[prefix for prefix in ('','source/') if observed==metadata|aux|{prefix+n for n in source['files']}]
        need(len(layouts)==1,'exactly one complete extracted source layout required')
        prefix=layouts[0]
        for name,row in source['files'].items():
            raw=read_regular(code/(prefix+name),row['bytes'])
            need(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'extracted source member differs')
            files[name]=raw
        archive_raw=zip_source(files)
        need(len(archive_raw)==arch['bytes'] and digest(archive_raw)==archive_sha256,'reconstructed exact raw source archive differs')
        mode='verified-extracted-source-directory' if prefix else 'verified-extracted-root'
    auxiliary={}
    for name,row in manifest['auxiliary_files'].items():
        raw=read_regular(code/name,row['bytes'])
        need(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'auxiliary deployment/review bytes differ')
        auxiliary[name]=raw
    return manifest,files,auxiliary,archive_raw,mode


def load_release(code_root, source_parent, *, manifest_sha256, archive_sha256):
    code=clean_path(code_root);parent=clean_path(source_parent)
    need(not parent.exists() and not parent.is_relative_to(code) and not code.is_relative_to(parent),'fresh disjoint source parent required')
    manifest,files,auxiliary,archive_raw,mode=inspect_release(code,manifest_sha256=manifest_sha256,archive_sha256=archive_sha256)
    parent.mkdir(parents=True,exist_ok=False)
    source=parent/'runtime';source.mkdir()
    for root,blobs in ((source,files),(parent,auxiliary)):
        for name,raw in blobs.items():
            path=root/safe_name(name);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(raw)
    with (parent/'source.zip').open('xb') as stream:stream.write(archive_raw)
    receipt={'format':'irisx/rlvr-no-model-source-acceptance-v1','source_root':str(source),'deployment_root':str(parent/'deployment'),
             'source_archive_path':str(parent/'source.zip'),'material_root':str(parent/'release'),
             'source_sha256':manifest['source']['source_sha256'],'source_archive_sha256':archive_sha256,
             'manifest_sha256':manifest_sha256,'source_transport_mode':mode,'original_archive_transport':mode=='verified-archive',
             'exact_archive_bytes_available':True,'source_members':len(files),'auxiliary_members':len(auxiliary),
             'model_imported':False,'weights_read':False,'evaluator_body_read':False,'provider_mount_verified':False}
    with (parent/'source-acceptance.json').open('xb') as stream:stream.write(encoded(receipt))
    return receipt


def source_import_paths(source):
    """Fresh verified source has no bytecode execution surface; prohibit caches."""
    import sys
    source=clean_path(source)
    for path in source.rglob('*'):
        need(not path.is_symlink(),'source import symlink')
        need(path.name!='__pycache__' and path.suffix not in ('.pyc','.pyo'),'source bytecode cache forbidden')
    sys.dont_write_bytecode=True
    sys.path[:0]=[str(source),str(source/'baseline'),str(source/'baseline/src')]
