"""Deterministic complete-source ZIP and full byte roundtrip, local only."""
from pathlib import Path
import argparse,hashlib,json,stat,zipfile

def need(ok,message):
    if not ok:raise ValueError(message)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    need(not a.archive.exists() and not a.receipt.exists(),'fresh archive and receipt required')
    files={}
    for f in sorted(a.package.rglob('*')):
        need(not f.is_symlink(),'package link forbidden')
        if f.is_dir():continue
        st=f.stat();need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and stat.S_IMODE(st.st_mode)==0o644,'regular0644 single-link member')
        files[f.relative_to(a.package).as_posix()]={'bytes':st.st_size,'sha256':sha(f)}
    a.archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
        for name,row in files.items():
            f=a.package/name;b=f.read_bytes();need(len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256'],'member changed before archive')
            info=zipfile.ZipInfo(name,(2026,10,12,0,0,0));info.create_system=3;info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,b,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(a.archive) as z:
        need(z.namelist()==list(files) and len(z.namelist())==len(set(z.namelist())),'closed deterministic inventory')
        for info in z.infolist():
            b=z.read(info);need({'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==files[info.filename],'full ZIP member roundtrip')
            need(info.date_time==(2026,10,12,0,0,0) and info.create_system==3 and info.external_attr>>16==(stat.S_IFREG|0o644) and not info.extra and not info.comment,'canonical outer ZIP metadata')
    result={'format':'irisx/rlvr-owner-complete-source-archive-v1','status':'FULL_BYTE_ROUNDTRIP_PASS','archive':{'path':str(a.archive),'bytes':a.archive.stat().st_size,'sha256':sha(a.archive)},'members':len(files),'expanded_bytes':sum(v['bytes'] for v in files.values()),'file_inventory_sha256':sha(a.package/'FILE-INVENTORY.json'),'full_file_manifest_sha256':sha(a.package/'FULL-FILE-MANIFEST.json'),'source_only':True,'Git_provider_Library_model_calls':0}
    a.receipt.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
