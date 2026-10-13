"""Stdlib-only notebook loader. Nothing is read or written until explicitly called."""
from __future__ import annotations

def load_reviewed_qwen_source(*, pins, input_root, code_root, data_root, training_root, source_parent, output_root, model_config, resume=False):
    import hashlib, json, os, stat, sys, zipfile
    from pathlib import Path, PurePosixPath
    def need(value,message):
        if not value:raise ValueError(message)
    def path(value,absolute=False):
        need(type(value) is str and value and len(value)<=4096 and not any(ord(c)<32 for c in value),'invalid path')
        need('\\' not in value and ':' not in value and '..' not in value.split('/'),'ambiguous/traversing path')
        need(not absolute or value.startswith('/'),'absolute input root required')
        return Path('/'+os.path.abspath(value).lstrip('/'))
    def overlap(a,b):return a==b or a in b.parents or b in a.parents
    def links(p):
        for q in (*reversed(p.parents),p):need(not q.is_symlink(),'symlink path forbidden')
    def read(p,limit):
        links(p);need(stat.S_ISREG(p.stat().st_mode) and p.stat().st_size<=limit,'bounded regular file required')
        return p.read_bytes()
    def sha(raw):return hashlib.sha256(raw).hexdigest()
    def member_cap(name):
        return 12*1024**2 if name == 'materials/qwen14b/hf-overlay/tokenizer.json' else 2*1024**2
    def pairs(rows):
        result={}
        for k,v in rows:
            need(k not in result,'duplicate JSON key');result[k]=v
        return result
    def parse(raw):return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    need(type(resume) is bool,'exact Boolean resume required')
    need(type(model_config) is dict and set(model_config)<= {'input_root','explicit_roots'},'invalid model config')
    explicit=model_config.get('explicit_roots',{})
    need(type(explicit) is dict and set(explicit)<= {'runtime','model','wheels','interpreter','adapter'},'unknown model root')
    inputs=[path(input_root,True),path(model_config.get('input_root',input_root),True)]
    inputs += [path(v,True) for v in explicit.values() if v is not None]
    for value in (code_root,data_root,training_root):
        if value is not None:inputs.append(path(value,True))
    source_parent,path_output=path(source_parent),path(output_root)
    environment=path_output.parent/(path_output.name+'-environment')
    writes=[source_parent,path_output,environment]
    # Finish all lexical comparisons before any filesystem inspection or write.
    for target in writes:
        for immutable in inputs:need(not overlap(target,immutable),'write path overlaps immutable input')
    for i,a in enumerate(writes):
        for b in writes[i+1:]:need(not overlap(a,b),'source/output/environment overlap')
    for target in writes:links(target)
    def discover(reference,explicit_root):
        if explicit_root is not None:return path(explicit_root,True)
        owner,slug,version=reference.split('/')
        candidates=[inputs[0]/slug,inputs[0]/'datasets'/owner/slug]
        present=[p for p in candidates if p.is_dir()]
        need(len(present)==1,'exactly one pinned Dataset mount required: '+slug)
        return present[0]
    code=discover(pins['code']['reference'],code_root);data=discover(pins['data']['reference'],data_root)
    training=discover(pins['training']['reference'],training_root)
    links(code);links(data)
    code_raw=read(code/'manifest.json',1024*1024)
    need(sha(code_raw)==pins['code']['manifest_sha256'],'code manifest hash differs')
    manifest=parse(code_raw)
    need(manifest['format']=='irisx/learning-source-v1' and manifest['reference']==pins['code']['reference'],'code reference differs')
    archive=manifest['archive'];need(archive['name']=='source.zip','unexpected archive')
    need(archive['sha256']==pins['code']['archive_sha256'],'notebook source archive differs')
    data_raw=read(data/'public-data-material.json',1024*1024)
    need(sha(data_raw)==pins['data']['manifest_sha256'],'data material manifest differs')
    dm=parse(data_raw);need(dm['reference']==pins['data']['reference'] and dm['format']=='irisx/public120-data-material-v1','data reference differs')
    need(dm['role_manifests']==pins['data']['role_manifests'],'data role identities differ')
    # Training source has an independent exact closed inventory; no evaluator file is read.
    training_raw=read(training/'manifest.json',2*1024**2)
    need(sha(training_raw)==pins['training']['manifest_sha256'],'training manifest differs')
    tm=parse(training_raw)
    need(tm['format']=='irisx/learning-training-material-v1' and tm['reference']==pins['training']['reference'],'training source identity differs')
    need(tm['tasks']==1000 and tm['public_evaluation_files']==0,'clean1000 training profile required')
    need(len(tm['files'])<=1100 and sum(r['bytes'] for r in tm['files'].values())<=32*1024**2,'training material cap')
    observed_training=set()
    for member in training.rglob('*'):
        links(member)
        if member.is_file():observed_training.add(member.relative_to(training).as_posix())
        else:need(member.is_dir(),'nonregular training member')
    need(observed_training==set(tm['files'])|{'manifest.json'},'training inventory differs')
    for name,row in tm['files'].items():
        pure=PurePosixPath(name)
        need(not pure.is_absolute() and all(x not in ('','.','..') for x in name.split('/')) and '\\' not in name,'unsafe training member')
        body=read(training/name,2*1024**2)
        need(len(body)==row['bytes'] and sha(body)==row['sha256'],'training byte identity differs')
    # No evaluator member is opened here; evaluator validates it after sealing.
    files=manifest['files'];need(type(files) is dict and 1<=len(files)<=512,'source inventory ceiling')
    need(set(manifest['source_identity'])==set(files),'closed source identity required')
    for name,row in files.items():
        p=PurePosixPath(name)
        need(type(name) is str and not p.is_absolute() and '\\' not in name and ':' not in name and all(x not in ('','.','..') for x in name.split('/')),'unsafe source member')
        need(type(row['bytes']) is int and 0<=row['bytes']<=member_cap(name),'source member size')
        need(manifest['source_identity'][name]==row['sha256'],'source identity mismatch')
    need(sum(r['bytes'] for r in files.values())<=16*1024**2,'source expansion ceiling')
    content={}; allowed_metadata={'manifest.json','NOTICE.txt'}
    observed=set()
    for member in code.rglob('*'):
        links(member)
        if member.is_file():observed.add(member.relative_to(code).as_posix())
        else:need(member.is_dir(),'nonregular Dataset member')
    archive_path=code/'source.zip';links(archive_path)
    if archive_path.is_file():
        need(observed-allowed_metadata=={'source.zip'},'ambiguous archive and extracted source inventory')
        raw=read(archive_path,16*1024**2)
        need(sha(raw)==archive['sha256'] and len(raw)==archive['bytes'],'source archive integrity')
        import io
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members=z.infolist();need(len(members)==len(files) and len({m.filename for m in members})==len(members),'duplicate/extra archive members')
            need(sum(m.file_size for m in members)<=16*1024**2,'source expansion ceiling')
            for m in members:
                name=m.filename
                need(name in files,'unsafe archive member')
                need(stat.S_IFMT(m.external_attr>>16) in (0,stat.S_IFREG) and not m.is_dir() and m.file_size<=member_cap(name),'nonregular/large source member')
                value=z.read(m);need(len(value)==files[name]['bytes'] and sha(value)==files[name]['sha256'],'source file integrity')
                content[name]=value
        transport_mode='verified-archive'
    else:
        # Kaggle may extract an uploaded ZIP. Accept only these exact two
        # layouts, never recursive filename discovery or incomplete fallback.
        layouts=[('',code),('source/',code/'source')]
        matched=[(prefix,base) for prefix,base in layouts if observed-allowed_metadata=={prefix+n for n in files}]
        need(len(matched)==1,'exactly one closed extracted source inventory required')
        prefix,base=matched[0]
        for name,row in files.items():
            value=read(base/name,member_cap(name))
            need(len(value)==row['bytes'] and sha(value)==row['sha256'],'extracted source file integrity')
            content[name]=value
        transport_mode='verified-extracted-source' + ('-directory' if prefix else '-root')
    source=source_parent/archive['sha256'];links(source)
    if source.exists():
        actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}
        need(actual==set(content),'existing source inventory differs')
        for name,value in content.items():need(read(source/name,member_cap(name))==value,'existing source bytes differ')
    else:
        source.mkdir(parents=True,exist_ok=False)
        for name,value in content.items():
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(value);f.flush();os.fsync(f.fileno())
    for key,module in tuple(sys.modules.items()):
        if key=='tools' or key.startswith('tools.') or key=='irisx' or key.startswith('irisx.'):
            origin=getattr(module,'__file__',None)
            need(origin is not None and source in path(str(origin)).parents,'conflicting imported project source; restart kernel')
    sys.dont_write_bytecode=True
    sys.path[:0]=[str(source),str(source/'src')]
    entry_provenance={'format':'irisx/public120-notebook-source-admission-v1',
        'code_reference':pins['code']['reference'],'code_manifest_sha256':pins['code']['manifest_sha256'],
        'source_archive_sha256':archive['sha256'],
        'source_identity_sha256':sha(json.dumps(manifest['source_identity'],sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()),
        'source_transport_mode':transport_mode,'source_archive_bytes_verified':transport_mode=='verified-archive',
        'data_reference':pins['data']['reference'],'data_material_manifest_sha256':pins['data']['manifest_sha256'],
        'solver_manifest_sha256':pins['data']['role_manifests']['solver'],
        'evaluator_manifest_sha256':pins['data']['role_manifests']['evaluator']}
    return {'training_root':str(training/'data/training'),'training_manifest_sha256':pins['training']['manifest_sha256'],
            'source_root':str(source),'solver_root':str(data/'solver'),'evaluator_root':str(data/'evaluator'),
            'solver_manifest_sha256':pins['data']['role_manifests']['solver'],'evaluator_manifest_sha256':pins['data']['role_manifests']['evaluator'],
            'output_root':str(path_output),'code_manifest_sha256':pins['code']['manifest_sha256'],
            'source_transport_mode':transport_mode,'source_archive_bytes_verified':transport_mode=='verified-archive',
            'entry_provenance':entry_provenance}
