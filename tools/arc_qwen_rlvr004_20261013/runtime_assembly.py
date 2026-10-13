"""Reconstruct every exact runtime member from the complete owner repository."""
from pathlib import Path
import argparse,hashlib,io,json,stat,zipfile

def main():
    p=argparse.ArgumentParser();p.add_argument('--repository-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
    here=Path(__file__).resolve().parent;mapping=json.loads((here/'runtime-path-map.json').read_bytes());files={}
    if a.output_root.exists():raise ValueError('fresh output required')
    for name,row in mapping['files'].items():
        path=a.repository_root/row['repository_path']
        if any(q.is_symlink() for q in (path,*path.parents)):raise ValueError('source link')
        data=path.read_bytes()
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('source byte mismatch: '+name)
        files[name]=data
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,10,12,0,0,0));info.create_system=3;info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_STORED;archive.writestr(info,data)
    raw=stream.getvalue()
    if hashlib.sha256(raw).hexdigest()!=mapping['source_archive_sha256']:raise ValueError('exact reconstructed ZIP differs')
    a.output_root.mkdir(parents=True)
    for name,data in files.items():
        path=a.output_root/'producer-source'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (a.output_root/'source.zip').write_bytes(raw)
    print(json.dumps({'status':'EXACT_SOURCE_RECONSTRUCTION_PASS','members':len(files),'source_archive_sha256':mapping['source_archive_sha256'],'model_or_provider_calls':0}))

if __name__=='__main__':main()
