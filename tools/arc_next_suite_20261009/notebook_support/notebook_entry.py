import base64, hashlib, importlib.util, importlib.machinery, json, zlib
if type(MANUAL_START) is not bool:
    raise ValueError('Explicit Boolean manual switch required')
if not MANUAL_START:
    print('INACTIVE: '+RUN_ID+' saved. No installation, writes, model load, generation, training, dataset export or submission occurred.')
else:
    packed=base64.b64decode(PACKED_SOURCE_BASE64,validate=True)
    if hashlib.sha256(packed).hexdigest()!=PACKED_SOURCE_SHA256:raise ValueError('Embedded compressed source changed')
    decoder=zlib.decompressobj();raw=decoder.decompress(packed,UNPACKED_SOURCE_BYTES+1)
    if len(raw)!=UNPACKED_SOURCE_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('Embedded source size/stream differs')
    files=json.loads(raw)
    if set(files)!=set(FILE_HASHES):raise ValueError('Closed embedded source inventory differs')
    for name,value in files.items():
        if Path(name).name!=name or hashlib.sha256(value.encode()).hexdigest()!=FILE_HASHES[name]:raise ValueError('Embedded source hash/path differs')
    helper_bytes=NOTEBOOK_INPUT_HELPER_SOURCE.encode()
    if hashlib.sha256(helper_bytes).hexdigest()!=NOTEBOOK_INPUT_HELPER_SHA256:raise ValueError('Notebook input helper hash differs')
    BASE=BASE.absolute()
    immutable=[Path('/kaggle/input'),*map(Path,PRIOR_SEARCH_ROOTS)]
    immutable.extend(Path(globals()[role.upper()+'_ROOT']) for role in PINS if globals()[role.upper()+'_ROOT'])
    immutable.extend(Path(p) for p in PRIOR_RESULTS.values() if p)
    if any(p.is_symlink() for p in (BASE,*BASE.parents)) or any(BASE.resolve().is_relative_to(p.resolve()) for p in immutable):raise ValueError('Output must be non-symlink and outside every input')
    source=BASE/'source'
    if source.is_symlink():raise ValueError('Symlink source directory forbidden')
    source.mkdir(parents=True,exist_ok=True)
    for name,value in files.items():
        path=source/name
        if path.is_symlink():raise ValueError('Symlink source forbidden')
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=FILE_HASHES[name]:raise ValueError('Existing source differs')
        else:
            with path.open('xb') as stream:stream.write(value.encode())
    support=BASE/'notebook-support'
    if support.is_symlink():raise ValueError('Symlink notebook support directory forbidden')
    support.mkdir(exist_ok=True)
    helper_path=support/('arc_evidence_inputs-'+NOTEBOOK_INPUT_HELPER_SHA256+'.py')
    if helper_path.is_symlink():raise ValueError('Symlink notebook helper forbidden')
    if helper_path.exists():
        if hashlib.sha256(helper_path.read_bytes()).hexdigest()!=NOTEBOOK_INPUT_HELPER_SHA256:raise ValueError('Existing notebook helper differs')
    else:
        with helper_path.open('xb') as stream:stream.write(helper_bytes)
    class VerifiedLoader(importlib.machinery.SourceFileLoader):
        def __init__(self,name,path,data):super().__init__(name,str(path));self.data=data
        def get_code(self,fullname):return self.source_to_code(self.data,self.path)
    def load_verified(name,path,data):
        spec=importlib.util.spec_from_file_location(name,path,loader=VerifiedLoader(name,path,data))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    suite=load_verified('iris_suite_entry_'+FILE_HASHES['arc_suite.py'],source/'arc_suite.py',files['arc_suite.py'].encode())
    helper=load_verified('iris_notebook_inputs_'+NOTEBOOK_INPUT_HELPER_SHA256,helper_path,helper_bytes)
    result=helper.launch_notebook(suite,BASE,RUN_ID,prior_results=PRIOR_RESULTS,prior_search_roots=PRIOR_SEARCH_ROOTS,
        explicit_roots={role:globals()[role.upper()+'_ROOT'] for role in PINS},prior_dataset_pin=PRIOR_DATASET_PIN)
    print(json.dumps(result,ensure_ascii=False,indent=2))
