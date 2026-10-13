"""Portable, read-only, no-model complete package verification; no Git/network."""
from pathlib import Path
import hashlib,json,stat,zipfile
ROOT=Path(__file__).resolve().parent

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(path):
    need(not any(p.is_symlink() for p in (path,*path.parents)),'package symlink')
    s=path.stat();need(stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode)==0o644 and s.st_nlink==1 and s.st_size<=128*1024**2,'bounded regular package file')
    return path.read_bytes()
def main():
    inv=json.loads(read(ROOT/'FILE-INVENTORY.json'))
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}
    need(actual==set(inv)|{'FILE-INVENTORY.json'},'complete package file set')
    for name,row in inv.items():
        need('..' not in Path(name).parts and not Path(name).is_absolute(),'relative inventory name')
        b=read(ROOT/name);need(row=={'bytes':len(b),'sha256':sha(b)},'package member changed: '+name)
    full=json.loads(read(ROOT/'FULL-FILE-MANIFEST.json'));mapping=json.loads(read(ROOT/'repository/tools/arc_qwen_rlvr_20261012/runtime-path-map.json'))
    need(len(full['files'])==full['tracked_file_count'],'repository manifest count')
    for row in full['files']:
        b=read(ROOT/'repository'/row['path']);need(sha(b)==row['sha256'] and len(b)==row['bytes'] and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==row['git_blob_sha'],'repository blob identity')
    zraw=read(ROOT/'release/code-payload/source.zip');need(sha(zraw)==mapping['source_archive_sha256'],'exact producer ZIP')
    with zipfile.ZipFile(ROOT/'release/code-payload/source.zip') as z:
        need(len(z.namelist())==len(set(z.namelist()))==mapping['source_member_count']==259 and set(z.namelist())==set(mapping['files']),'exact runtime inventory')
        for name,row in mapping['files'].items():
            b=read(ROOT/'repository'/row['repository_path']);need(b==z.read(name) and len(b)==row['bytes'] and sha(b)==row['sha256'],'complete logical runtime mapping: '+name)
    print(json.dumps({'status':'COMPLETE_PACKAGE_AND_RUNTIME_MAPPING_PASS','repository_files':len(full['files']),'runtime_members':259,'source_archive_sha256':mapping['source_archive_sha256'],'model_or_provider_calls':0,'Git_HEAD_remote_or_clean_status_checked':False},sort_keys=True))
if __name__=='__main__':main()
