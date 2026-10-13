"""No-model acceptance against actual immutable assembled release bytes."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,sys,types,zipfile
from unittest.mock import patch
sys.dont_write_bytecode=True

def need(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def module(path,name):
    m=types.ModuleType(name);m.__file__=str(path.absolute());m.__package__='';sys.modules[name]=m
    exec(compile(path.read_bytes(),str(path.absolute()),'exec',dont_inherit=True),vars(m));return m
def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.candidate.absolute();out=a.output.absolute();need(not out.exists(),'fresh acceptance evidence root required');out.mkdir(parents=True)
    inventory=json.loads((root/'ASSEMBLY-INVENTORY.json').read_bytes());actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    need(actual==set(inventory)|{'ASSEMBLY-INVENTORY.json'},'closed assembled inventory')
    for name,row in inventory.items():
        b=(root/name).read_bytes();need(len(b)==row['bytes'] and sha(b)==row['sha256'],'exact assembled member')
    publication=json.loads((root/'publication-manifest.json').read_bytes());release=json.loads((root/'notebook-release.json').read_bytes())
    inert=[]
    for row in publication['notebooks']:
        raw=(root/row['path']).read_bytes();need(sha(raw)==row['sha256'] and len(raw)==row['bytes'],'actual inert notebook pin')
        n=json.loads(raw);scope={}
        with patch('builtins.open',side_effect=AssertionError('inert notebook attempted filesystem I/O')):
            for cell in n['cells']:
                if cell['cell_type']=='code':exec(compile(''.join(cell['source']),'<actual-inert-notebook>','exec'),scope)
        need(scope['MANUAL_START'] is False and scope['ENABLE_MODEL'] is False and scope['PREDISPATCH_EPOCH'] is None and scope['RESULT']['status']=='INACTIVE_NO_EXECUTION','inert actual notebook')
        inert.append({'path':row['path'],'sha256':sha(raw),'actual_cells_executed':True,'filesystem_accessed':False,'model_loaded':False})
    f=module(root/'assembly/finalize.py','checked_actual_finalizer')
    # This fixed expired epoch is explicitly a byte fixture, never a launch epoch.
    docs=f.finalize(root,1234567890);need(docs==f.finalize(root,1234567890),'pure deterministic actual JIT')
    expected=(root/'consumer-release/release.json').read_bytes();staged=root.parent/'consumer-binding-final-001/release.json'
    if staged.exists():need(expected==staged.read_bytes(),'preconsumer and final release byte identity')
    accept=module(root/'assembly/accept_downloaded_mount.py','checked_actual_mount_acceptance');results={}
    payload=root/'code-payload'
    for layout in ('original-upload','extracted-root','extracted-source-directory'):
        mount=out/(layout+'-mount');shutil.copytree(payload,mount)
        if layout!='original-upload':
            zpath=mount/'source.zip'
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    target=mount/('source' if layout=='extracted-source-directory' else '')/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
            zpath.unlink()
        results[layout]=accept.accept(root,mount,out/(layout+'-acceptance'))
        need(results[layout]['isolated_import']['source_sha256']==publication['runtime_source_sha256'] and results[layout]['source_acceptance']['source_members']==259,'actual complete259 source import')
    damaged=out/'extracted-root-mount/owned_runtime/release.py';old=damaged.read_bytes();damaged.write_bytes(old+b'\n# mutation\n')
    try:accept.accept(root,damaged.parents[1],out/'negative-source-mutation')
    except ValueError:mutation_rejected=True
    else:raise AssertionError('source mutation accepted')
    finally:damaged.write_bytes(old)
    report={'format':'irisx/rlvr-final-assembly-cpu-acceptance-v1','status':'PASS','publication_manifest_sha256':sha((root/'publication-manifest.json').read_bytes()),'assembly_inventory_sha256':sha((root/'ASSEMBLY-INVENTORY.json').read_bytes()),'source_sha256':publication['runtime_source_sha256'],'inert_notebooks':inert,'fixed_epoch_JIT_fixture_only':True,'JIT_output_sha256':{n:sha(b) for n,b in docs.items()},'actual_source_layouts':{k:{'status':r['status'],'mode':r['source_acceptance']['source_transport_mode'],'source_sha256':r['isolated_import']['source_sha256']} for k,r in results.items()},'source_mutation_rejected':mutation_rejected,'actual_provider_mount_verified':False,'provider_readback_acceptance_still_required':True,'model_or_GPU_calls':0,'provider_calls':0,'evaluator_body_reads':0}
    (out/'ASSEMBLY-ACCEPTANCE.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');print(json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
