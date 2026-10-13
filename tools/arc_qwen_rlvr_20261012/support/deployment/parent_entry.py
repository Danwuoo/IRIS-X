"""Pinned installed parent calls the genuine reviewed owned-runtime entrypoint."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
import types
def _source_module(name):
    path=HERE/(name+'.py');module=types.ModuleType(name);module.__file__=str(path);module.__package__=''
    sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(module))
    return module
_source_module('source_loader')
from source_loader import read_regular,parse,digest,need,clean_path,encoded,source_import_paths


def main():
    need(len(sys.argv)==3,'exact installed-parent request and hash required')
    raw=read_regular(Path(sys.argv[1]),2*1024**2);need(digest(raw)==sys.argv[2],'installed-parent request bytes differ')
    request=parse(raw);need(request['format']=='irisx/rlvr-installed-parent-request-v1','installed parent schema')
    source=clean_path(request['source_root'])
    source_import_paths(source)
    from owned_runtime.release import inventory,source_digest
    need(source_digest(inventory())==request['source_sha256'],'parent full source identity differs')
    from owned_runtime.bootstrap import reviewed_bootstrap
    result=reviewed_bootstrap(request['config'],request['output_root'],**request['paths'])
    with Path(request['result_path']).open('xb') as stream:stream.write(encoded(result))
    print(encoded({'status':result['status'],'terminal_status':result.get('terminal_export',{}).get('status')}).decode(),flush=True)
    if result['status'] not in ('owned-mechanics-complete-PUBLIC-sealed','owned-mechanics-partial-comparison-PUBLIC-sealed') or result.get('terminal_export',{}).get('status')!='complete':
        raise SystemExit(1)

if __name__=='__main__':main()
