"""Accept exact downloaded code17 mount bytes without model/evaluator execution.

Provider provenance comes from the independent numeric-version transport receipt;
this helper only verifies the actual local mount content supplied by that caller.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,types


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def accept(candidate_root,code_root,output_root):
    candidate=Path(candidate_root).absolute();output=Path(output_root).absolute()
    need(not output.exists() and not any(p.is_symlink() for p in (output,*output.parents)),'fresh ordinary acceptance output required')
    release=json.loads((candidate/'notebook-release.json').read_bytes())
    path=candidate/'code-payload/deployment/source_loader.py'
    need(sha(path.read_bytes())==release['deployment']['source_loader.py']['sha256'],'externally bound loader bytes differ')
    loader=types.ModuleType('accept_rlvr_mount');loader.__file__=str(path);loader.__package__=''
    sys.modules[loader.__name__]=loader
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(loader))
    output.mkdir()
    receipt=loader.load_release(str(Path(code_root).absolute()),str(output/'source'),manifest_sha256=release['code_manifest_sha256'],archive_sha256=release['source_archive_sha256'])
    # Isolated source-only executable import closure check. No tensor library.
    worker=output/'source-check.py'
    worker.write_text('''from pathlib import Path
import json,sys
root=Path(sys.argv[1]);sys.path[:0]=[str(root),str(root/'baseline'),str(root/'baseline/src')]
from owned_runtime.release import inventory,source_digest,closed_bootstrap
closed_bootstrap()
from owned_runtime.bootstrap import reviewed_bootstrap
from owned_runtime.parent_scoring import validate_model_config
from owned_runtime.planning import build_plan
if any(name in sys.modules for name in ('torch','transformers','peft')):raise ValueError('model library imported during source-only acceptance')
print(json.dumps({'source_sha256':source_digest(inventory()),'reviewed_bootstrap_module':reviewed_bootstrap.__module__,'source_only':True,'model_libraries_imported':False},sort_keys=True))
''')
    proc=subprocess.run([sys.executable,'-I','-B',str(worker),receipt['source_root']],cwd=output,env={'PATH':os.defpath,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,check=False)
    (output/'stdout.txt').write_bytes(proc.stdout);(output/'stderr.txt').write_bytes(proc.stderr)
    need(proc.returncode==0,'isolated no-model source import failed')
    checked=json.loads(proc.stdout);need(checked['source_sha256']==release['source_sha256'],'actual extracted executable source identity differs')
    result={'format':'irisx/rlvr-actual-local-code-mount-acceptance-v1','status':'PASS','source_acceptance':receipt,'isolated_import':checked,
        'actual_code_root':str(Path(code_root).absolute()),'expected_code_reference':release['code_reference'],
        'production_execution_claim':False,'provider_provenance_verified_by_this_helper':False,'external_numeric_download_receipt_required':True,
        'public_evaluator_body_reads':0,'model_or_GPU_calls':0,'provider_calls':0}
    (output/'receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate-root',type=Path,required=True);p.add_argument('--code-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
    print(json.dumps(accept(a.candidate_root,a.code_root,a.output_root),sort_keys=True))

if __name__=='__main__':main()
