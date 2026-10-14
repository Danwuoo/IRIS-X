"""Rebuild authentic historical run007 and inert run008 source, offline only.

Run only with the separately obtained original authentic-inputs archive in an
isolated workspace. Original validators may stream opaque evaluator archives
for integrity; they never semantically parse answers. No native operator,
provider, authentication, model, scoring, owner approval or real clock is invoked.
Missing inputs remain a failure. Existing output directories are never replaced.
"""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import stat, subprocess, sys

SNAPSHOT='e951604b829497e81bc6e18b32662ff050bd54db'
TREE='f9b10d12b912f3a92238375451c0ad56d4cb7efb'
PROPOSAL_INVENTORY='fc32f98bef4188761fd51275bb05dd26c6fbd237afb8b8403b492f61442055cd'
REBUILD_REPORT='3645c2321618476401242f3f2684c82c08f15978f894fae88b76574a7ab0cf04'
SOURCE='c61025e67354272099e40941cadcd77202964846d9a4c42c51a1817f77bb661b'
ARCHIVE='4d8b414bd35ca79a2eaaec7042880966879ed13bdeaf96762eaee7932ee1de4c'
MANIFEST='1d3aabee0419acd2b42a4343d36028b0ba296f14f30341e5be8e6c83e42600f0'
REVIEW='ffb141edfc37a357b73939000d113d78ff5775922c868d602e9e619fd1ac7bab'

def need(ok, message):
    if not ok: raise ValueError(message)
def regular(path):
    path=Path(path)
    need(path.is_absolute() and '..' not in path.parts,'explicit absolute normal path required')
    need(all(not p.is_symlink() for p in (path,*path.parents)),'linked input/output denied')
    return path
def digest(path):
    path=regular(path);info=path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'single-link regular input required')
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def run(command, repo, env):
    # Only the fixed git object read and two fixed offline repository scripts
    # are constructed below. Never accepts a caller-supplied program.
    subprocess.run(command,cwd=repo,env=env,stdin=subprocess.DEVNULL,check=True)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repository-root',required=True,type=Path)
    ap.add_argument('--authentic-inputs-root',required=True,type=Path)
    a=ap.parse_args();repo=regular(a.repository_root);inputs=regular(a.authentic_inputs_root)
    need(os.name=='posix' and sys.version_info[:2]==(3,12),'POSIX Python 3.12 required')
    need((repo/'.git').exists() and (inputs/'run007').is_dir(),'Git checkout and authentic-inputs/run007 required')
    env=dict(os.environ);env.update(PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',GIT_NO_LAZY_FETCH='1')
    tree=subprocess.check_output(['git','-C',str(repo),'rev-parse',SNAPSHOT+'^{tree}'],stdin=subprocess.DEVNULL,env=env).decode().strip()
    need(tree==TREE,'required original Git snapshot tree missing or changed')
    tool=repo/'tools/arc_qwen_rlvr004_20261013'
    base=repo/'.irisx/transfer-verification-20261013/rebuild-offline-2'
    proposal=repo/'.irisx/run008-packaging/independent-reviewed-proposal'
    need(not base.exists() and not proposal.exists() and not (repo/'.irisx/RUN008-ENGINEERING-REBUILD-REPORT.json').exists(),'preserve prior results; use a fresh checkout when fixed test-input roots exist')
    need(not inputs.is_relative_to(base) and not inputs.is_relative_to(proposal),'input/output overlap denied')
    overlay=tool/'loader_repair_run008/OVERLAY-MANIFEST.json'
    review=repo/'research/native-continuation-20261013/independent-loader-review.json'
    need(digest(overlay)==MANIFEST and digest(review)==REVIEW,'exact published overlay/review required')
    (repo/'.irisx').mkdir(exist_ok=True)
    run([sys.executable,'-B',str(tool/'transfer_handoff_20261014/rebuild_portable.py'),'--repository-root',str(repo),'--inputs-root',str(inputs),'--output-root',str(base)],repo,env)
    need(digest(base/'REBUILD-REPORT.json')==REBUILD_REPORT,'historical rebuild report differs')
    run([sys.executable,'-B',str(tool/'run008_successor/prepare.py'),'--repository-root',str(repo),'--candidate-root',str(base/'candidate-rebuild'),'--source-proposal-root',str(base/'source-rebuild'),'--rebuild-report',str(base/'REBUILD-REPORT.json'),'--output-root',str(proposal),'--overlay-manifest',str(overlay),'--overlay-manifest-sha',MANIFEST,'--overlay-review',str(review),'--overlay-review-sha',REVIEW],repo,env)
    need(digest(proposal/'ASSEMBLY-INVENTORY.json')==PROPOSAL_INVENTORY,'exact inert run008 proposal inventory differs')
    d=json.loads((proposal/'ASSEMBLY-PROPOSAL.json').read_text())
    need(d['source_sha256']==SOURCE and d['source_archive_sha256']==ARCHIVE and d['successor_epoch'] is None,'source/archive or inert state differs')
    expected=json.loads((proposal/'ASSEMBLY-INVENTORY.json').read_text())
    actual={p.relative_to(proposal).as_posix() for p in proposal.rglob('*') if p.is_file()}
    need(actual==set(expected)|{'ASSEMBLY-INVENTORY.json'},'inert proposal file closure differs')
    for name,row in expected.items():
        p=proposal/name
        need(p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],'inert proposal member differs: '+name)
    report={'format':'irisx/run008-portable-engineering-rebuild-v1','status':'PASS','run007_source_files':283,'run007_candidate_files':426,'run008_source_proposal_files':len(actual),'source_proposal_inventory_sha256':PROPOSAL_INVENTORY,'runtime_source_sha256':SOURCE,'runtime_archive_sha256':ARCHIVE,'provider_calls':0,'model_or_GPU_calls':0,'answer_bodies_semantically_parsed':False,'original_proof_bytes_rewritten':False,'new_owner_direction_created':False,'new_admitted_candidate_created':False,'run008_epoch':None,'scope':'Authentic historical reconstruction and inert source proposal only; not launch authority.'}
    out=repo/'.irisx/RUN008-ENGINEERING-REBUILD-REPORT.json'
    with out.open('x') as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
