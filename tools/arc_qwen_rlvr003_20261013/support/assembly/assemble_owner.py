"""Full baseline-preserving owner handoff. No Git/provider/Library/model actions."""
from pathlib import Path
import argparse,hashlib,importlib.util,io,json,os,re,shutil,stat,sys,zipfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
BASE=ROOT.parent
PRIOR=BASE/'portfolio63-rl-bootstrap-repair-20261013/owner-handoff/complete-source-rlvr002'
PRIOR_ZIP=PRIOR.parent/'iris-x-rlvr002-code15-complete-source-20261013.zip'
PRIOR_ZIP_SHA='552c0cc7d207ad8c1a78b04943cf653968ea7c895a399b3bf6147675cd3e8123'
DEP='tools/arc_qwen_rlvr003_20261013'
sys.path.insert(0,str(ROOT/'deployment'))
from source_loader import need,digest,encoded,safe_name,read_regular,zip_source


def raw(path):return read_regular(Path(path).absolute(),128*1024**2)
def put(path,value):
    path=Path(path);need(not path.exists(),'fresh handoff destination required: '+str(path));path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value);path.chmod(0o644)
def row(name,data):return {'path':name,'mode':'100644','bytes':len(data),'sha256':digest(data),'git_blob_sha':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()}


def build(release_root,out):
    release=Path(release_root).absolute();out=Path(out).absolute();need(not out.exists(),'fresh separate full-owner package required')
    need(digest(raw(PRIOR_ZIP))==PRIOR_ZIP_SHA,'exact already delivered rlvr002 code15 full-source predecessor')
    prior_doc=json.loads(raw(PRIOR/'FULL-FILE-MANIFEST.json'));prior={r['path']:r for r in prior_doc['files']}
    need(len(prior)==2261 and prior_doc['target_tree']=='1f08278b7ae75644531779ae2fcd59223d83d10f','exact complete owner2261 predecessor')
    spec=importlib.util.spec_from_file_location('owner_tree_verifier',PRIOR/'verify-owner-checkout.py');verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    need(verifier.tree(prior)==prior_doc['target_tree'],'prior offline Git tree encoding')
    blobs={}
    with zipfile.ZipFile(PRIOR_ZIP) as archive:
        for name,ref in prior.items():
            data=raw(PRIOR/'repository'/name)
            need(row(name,data)==ref and archive.read('repository/'+name)==data,'unchanged complete previous source: '+name)
            blobs[name]=data
    manifest=json.loads(raw(release/'publication-manifest.json'));freeze=json.loads(raw(release/'SOURCE-FREEZE.json'))
    need(manifest['source_review_only'] is False and manifest['release_runtime_finalized'] is True,'hold handoff seal until final publishable source revision')
    baseline_map=json.loads(raw(PRIOR/'repository/tools/arc_qwen_checkpoint_repair_deployment_20261012/runtime-path-map.json'))['files']
    mapping={}
    with zipfile.ZipFile(release/'code-payload/source.zip') as archive:
        need(set(archive.namelist())==set(freeze['files']),'final closed producer inventory')
        for name,ref in freeze['files'].items():
            data=archive.read(name);need(digest(data)==ref['sha256'] and len(data)==ref['bytes'],'final source byte identity')
            if name.startswith('baseline/'):
                logical=name[len('baseline/'):];need(logical in baseline_map,'unmapped baseline source')
                target=baseline_map[logical]['repository_path'];need(blobs[target]==data,'inherited baseline changed')
            else:
                target=DEP+'/source/'+safe_name(name);need(target not in blobs,'new logical source overlaps owner baseline');blobs[target]=data
            mapping[name]={'repository_path':target,'bytes':len(data),'sha256':digest(data),'mode':'100644'}
    # Complete final release bytes are separate from the commit-ready repository.
    release_blobs={p.relative_to(release).as_posix():raw(p) for p in sorted(release.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    for name,data in release_blobs.items():
        if name.startswith('producer-source/'):continue # Reconstruct via complete source mapping; exact source.zip is retained.
        put(out/'release'/name,data)
        # No archives/raw predecessor run receipts are staged into Git source.
        if not name.startswith(('predecessor/','code-payload/')) and not name.endswith('.zip'):
            target=DEP+'/release/'+name;need(target not in blobs,'release helper overlap');blobs[target]=data
    for folder in ('deployment','assembly','tests'):
        for p in sorted((ROOT/folder).rglob('*.py')):
            if '__pycache__' in p.parts:continue
            target=DEP+'/support/'+folder+'/'+p.relative_to(ROOT/folder).as_posix();need(target not in blobs,'source helper overlap');blobs[target]=raw(p)
    for p in sorted((ROOT/'publication').glob('*.py')):
        target=DEP+'/publication/'+p.name;need(target not in blobs,'publisher helper overlap');blobs[target]=raw(p)
    mapdoc={'format':'irisx/rlvr-logical-runtime-path-map-v1','source_sha256':freeze['source_sha256'],
        'source_archive_sha256':freeze['source_archive_sha256'],'source_member_count':len(mapping),
        'publication_manifest_sha256':digest(raw(release/'publication-manifest.json')),'files':mapping,
        'baseline200_exact':True,'new_files_only_under_tools':True,'source_mapping_not_runtime_admission':True}
    blobs[DEP+'/runtime-path-map.json']=encoded(mapdoc)
    blobs[DEP+'/runtime_assembly.py']=RUNTIME_ASSEMBLY.encode()
    for name,data in blobs.items():put(out/'repository'/name,data)
    put(out/'verify-owner-checkout.py',raw(PRIOR/'verify-owner-checkout.py'))
    actual={name:row(name,data) for name,data in sorted(blobs.items())};need(all(actual[n]==r for n,r in prior.items()),'prior snapshot must remain entirely unchanged')
    added=set(actual)-set(prior);need(all(n.startswith(DEP+'/') for n in added),'new source outside exact isolated successor prefix')
    owner=dict(prior)
    for entry in json.loads(raw(PRIOR/'CHANGED-VS-OWNER-BASE.json'))['files']:
        if entry['change']=='added':del owner[entry['path']]
        else:owner[entry['path']]=entry['baseline']
    need(verifier.tree(owner)==prior_doc['base_tree'],'last known owner base reconstruction')
    target=verifier.tree(actual)
    full={'format':'irisx/owner-complete-rlvr003-code16-source-v1','base_commit':prior_doc['base_commit'],'base_tree':prior_doc['base_tree'],
        'prior_delivered_tree':prior_doc['target_tree'],'target_tree':target,'tracked_file_count':len(actual),
        'remote_git_checked':False,'new_commit_exists':False,'files':list(actual.values())}
    put(out/'FULL-FILE-MANIFEST.json',encoded(full))
    for name,before in [('PRIOR-SNAPSHOT',prior),('OWNER-BASE',owner)]:
        delta=[{**r,'change':'added' if n not in before else 'modified','baseline':before.get(n)} for n,r in actual.items() if n not in before or r!=before[n]]
        doc={'format':'irisx/owner-rlvr003-changed-files-v1','comparison_tree':verifier.tree(before),'target_tree':target,
            'known_owner_base_commit':prior_doc['base_commit'],'deletions':[],'added':sum(x['change']=='added' for x in delta),
            'modified':sum(x['change']=='modified' for x in delta),'files':delta}
        put(out/('CHANGED-VS-'+name+'.json'),encoded(doc));put(out/('CHANGED-VS-'+name+'.txt'),''.join(r['path']+'\n' for r in delta).encode())
        put(out/('CHANGED-VS-'+name+'.git-pathspec'),''.join(':(literal)'+r['path']+'\n' for r in delta).encode())
    put(out/'README.zh-TW.md',README.encode())
    instructions=README+'\n\n'+MANUAL
    put(out/'OWNER-MANUAL-COMMIT-INSTRUCTIONS.zh-TW.md',instructions.encode())
    hygiene(out,added)
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.suffix=='.py':compile(p.read_bytes(),str(p),'exec')
    receipt={'format':'irisx/rlvr-full-owner-source-stage-v1','status':'STAGED_FOR_INDEPENDENT_REVIEW','prior_zip_sha256':PRIOR_ZIP_SHA,
        'prior_repository_files':len(prior),'prior_files_unchanged':len(prior),'prior_files_modified':0,'prior_files_deleted':0,
        'new_repository_files':len(added),'repository_files':len(actual),'target_tree':target,'source_members':len(mapping),
        'source_archive_sha256':freeze['source_archive_sha256'],'runtime_source_sha256':freeze['source_sha256'],
        'full_snapshot_not_patch_only':True,'new_model_weights_or_raw_gold':False,'git_provider_Library_model_calls':0,
        'complete_release_source_reconstructible':True,'top_level_omission':'producer-source materialization only; exact full source.zip and complete logical map retained'}
    put(out/'STAGING-RECEIPT.json',encoded(receipt))
    put(out/'verify-package.py',raw(HERE/'verify_package.py'))
    allfiles={p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':digest(raw(p))} for p in sorted(out.rglob('*')) if p.is_file()}
    put(out/'FILE-INVENTORY.json',encoded(allfiles));return receipt


def hygiene(root,newpaths):
    secrets={'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----','github_token':rb'\b(?:ghp|github_pat)_[A-Za-z0-9_]{25,}',
        'aws_key':rb'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b','signed_url':rb'https?://[^\s\"<>]+[?&](?:X-Amz-Signature|X-Goog-Signature|sig|access_token)=[^\s\"<>]+',
        'bearer':rb'Bearer [A-Za-z0-9_.-]{40,}'}
    forbidden={'.git','__pycache__','.aws','.env','.netrc','.kaggle-oauth-home','kaggle.json','credentials.json'}
    def scan(name,data,depth=0):
        need(not any(p in forbidden for p in Path(name).parts),'forbidden file in handoff')
        for key,pattern in secrets.items():need(re.search(pattern,data,re.I if key=='signed_url' else 0) is None,'secret pattern '+key+' in '+name)
        if name.endswith('.zip'):
            need(depth<4,'nested source archive depth')
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names=archive.namelist();need(len(names)==len(set(names)),'duplicate nested ZIP member')
                for info in archive.infolist():
                    safe_name(info.filename);need(not info.is_dir() and info.file_size<=64*1024**2,'source-only nested member bound')
                    need(Path(info.filename).suffix not in ('.pt','.pth','.safetensors','.pkl','.pickle'),'model tensor in source archive')
                    scan(name+'!'+info.filename,archive.read(info),depth+1)
    for p in sorted(root.rglob('*')):
        need(not p.is_symlink(),'handoff link forbidden')
        if p.is_file():scan(p.relative_to(root).as_posix(),raw(p))
    put(root/'HYGIENE-RECEIPT.json',encoded({'format':'irisx/rlvr-owner-hygiene-v1','status':'PASS','credentials_or_signed_urls_detected':False,
        'new_raw_gold_or_model_weights':False,'inherited_repository_bytes_preserved':True,'qualification':'Pattern checks are bounded hygiene checks, not a universal proof about all inherited content.'}))


RUNTIME_ASSEMBLY='''"""Reconstruct every exact runtime member from the complete owner repository."""
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
'''
README='''# IRIS-X rlvr003 / code16 完整來源交接

這是獨立的新來源快照，保留先前已交付 rlvr002 / code15 repository 的全部2261個檔案，既有檔案沒有修改或刪除。新增的 RLVR、部署、驗證與研究來源全部只位於 tools/arc_qwen_rlvr003_20261013/；不修改其他路徑。這不是只含 patch 的來源包，也未替你建立 commit 或 push。

v29 已通過先前的 library path 與 stdlib 安裝前驗證修正，但 production dataset 設定在模型載入前缺少 public_exclusions_sha256 而失敗。本次修正 backend 內部的來源綁定資料契約，並修正外部 wrapper verifier 對 terminal authorization 的巢狀 schema 讀取。先前啟動修正、安裝後完整 NumericGate、A/B/C 數值方法與原始評分器保持不變。v29 的 parent 程序已結束，但缺少 authenticated model journal，不能宣稱模型安全封閉、比較有效、達標或成本完整。所有既有來源與失敗證據均保留。

發布前已以實際 training1 完整1000筆來源執行 nonfixture CPU 資料建構；獨立比較確認 solver、source receipts、records、plan、cases 與原始 escrow 雜湊一致，只允許兩個明示輸出路徑替換。這是資料與程式契約驗證，不是14B模型訓練或成績。完整 runtime 的資料完整性負面測試及獨立最終來源審查仍以交接內精確綁定的 receipt 為準。

A 是同一次 session 重訓的 SFT256；B 是固定4批、每批8parents×G8、最多4次更新；C 從 A 續訓並以 B 的完整額外模型階段時間配對。全部32個預定 parent 需明列是否執行。科學條件、held32已使用過的限制、未完成及未匹配狀態都保留。實作中的成本預估只在每批完整64個 slot 的邊界更新單調 cost floor，避免第一個冷啟動 call 永久支配預估。封存 PROPOSAL.md 內 revision2 的 per-sample prefix 及「仍需整合」段落是歷史說明；最終 v3 POLICY.json 與精確 runtime source 才是現行規則，封存歷史文件沒有改写。

兩份 notebook 預設 MANUAL_START=False、ENABLE_MODEL=False、PREDISPATCH_EPOCH=None。private code16、inactive30 與 active31 是本次發布身分；ZIP 本身不代表 provider 已發布或已執行。啟動仍需獨立核准與單一新 epoch 的 JIT 完整文件重建，不可只修改一個時間文字。

所有排隊、離線安裝、模型工作、評分及封存共用原始 epoch；inner42000、outer42180、provider42300、absolute43200秒不重設。僅使用原本 Qwen14B BF16／FP32 LoRA、既有單卡與固定材料；沒有 FP8、4L4 或新資源。

release/ 包含完整發布來源與獨立 consumer 文件；producer-source 的可重建展開副本沒有重複打包。完整 producer source.zip 已保留，每個 logical path 也映射至 repository 的實際完整檔案：tools/arc_qwen_rlvr003_20261013/runtime-path-map.json。

不載入模型的精確重建：

python -B repository/tools/arc_qwen_rlvr003_20261013/runtime_assembly.py --repository-root /absolute/package/repository --output-root /absolute/new-scratch

這会重建相同 SHA256 的 source.zip 及完整 producer-source，不連網、不讀 evaluator 答案、不執行模型。CPU tiny／合成管線測試不是14B成績。原始 scorer 的 micro pass@2 ≥151/167 仍是唯一 PUBLIC目標，缺失或無效答案視為錯誤；Kaggle COMPLETE 與達標不是同一件事。

證據預設下載緊湊 evidence ZIP 與外部 terminal JSON。checkpoint ZIP 預設僅確認 header/presence，沒有下載的 tensor body 不得宣稱雜湊驗證。完整檢查由另行外部綁定的 terminal consumer 執行，consumer 不在 producer inventory 內。

沒有新 gold、模型權重、認證資料、signed URL 或原始工具回應。既有歷史 repository 檔案原樣保留。安裝環境位於 /tmp，不加入 Kaggle saved outputs，但仍需通過所在檔案系統的實際磁碟檢查。

來源內的 production_admitted、publishable、goal_met=false 及 legacy source-review scope 僅為不具權限的內容標記，不表示實際後端是 CPU。實際 backend_scope、環境與 native 身分由原始 receipt 記錄；最終 production、comparison、PUBLIC metric 及 goal 軸只能由外部綁定的 consumer 驗證後給出。部分比較正常結束可有完整有效 PUBLIC 分數，不能自行宣稱 comparison complete。
'''
MANUAL='''## 手動 commit 步驟

1. 先保留你的工作與未提交變更。在任何複製或 stage 前，檢查 git status --porcelain=v1 --untracked-files=all、git ls-files -u、git rev-parse HEAD、git rev-parse HEAD^{tree}、git branch --show-current 及 git remote -v。若有 staged、unstaged、untracked 或 merge conflict，先停止，在另一個乾淨的 owner checkout 人工整合；不可 reset、clean、stash 或覆蓋尚未保存的工作。確認 origin 是你核准的 private repository，branch 是你指定的目標，且沒有進行中的 merge/rebase。任一無法確認就停止。這些是必要人工 gate，raw-file verifier 不會替你查 HEAD 或 remote。
2. 若 checkout 已是上次 rlvr002 / code15 完整快照，HEAD tree 必須為 1f08278b7ae75644531779ae2fcd59223d83d10f，且其 commit/branch 由你確認，使用 prior-snapshot。若使用 owner-base，HEAD 必須正好是 08d6e1c7a7feae044fdd50e6d421b4a7340ea56a，tree 必須為 c5fe7208190e2fca349296ba92ff5ecc01ad101e。不同 base、錯誤或未知 private origin、衝突及本地變更都必須先停止；不要為了通過檢查而更改歷史。

python -B /absolute/package/verify-owner-checkout.py --repo /absolute/your-checkout --phase before --baseline prior-snapshot

任一不符先停止、人工比對，不要覆蓋本地工作。這個檢查不代替 Git status，也不證明目前遠端狀態。

3. 根據對應 CHANGED-VS-*.txt 逐項複製來源到 checkout；不要覆蓋 unrelated files。完整 repository/ 提供可對照的全量來源。
4. 必要的 portable checks：先用 python -B /absolute/package/verify-package.py 檢查完整檔案清單、source ZIP 及259項來源映射；複製後用 verify-owner-checkout.py --phase after 檢查目標 raw tree；執行上述 runtime_assembly.py 精確重建；以 python -B -m unittest discover -s repository/tools/arc_qwen_rlvr003_20261013/support/tests -p test_deployment.py（以及 -O -B）執行23項無模型部署/JIT/快取邊界測試。新 package 的 immutable byte checks 不會替代 Git status gate。

其餘 support/tests/test_startup_repair.py、support/assembly/build_release.py、assemble_owner.py 與 environment／raw-wrapper proof harness 保留作者原始 workspace 路徑及前置材料，列為 author-only 重現來源，不宣稱可直接在你的 checkout 執行。它們需要先前完整來源包、sibling portfolio63-rl-data-repair-20261013 的 frozen source ZIP、environment-candidate、CPU raw proof fixtures 等原始材料。publication/ 的 operator/collector 也保留完整來源，但執行需要原本已審查的操作環境、session/readback/stop 狀態及當次獨立核准；本來源包不包含認證，也不是跳過核准的啟動捷徑。完整歷史 aggregate tests、完整14B／GPU／provider 實機測試不包含在本次 portable 檢查中，沒有重跑或通過的新主張；原有封存測試與獨立審查另行保留。不要把 compile、CPU tiny 或合成測試當作 benchmark 成績。
5. 確認新增／修改清单無誤後，手動使用對應的 literal pathspec 檔案 stage：

git add --pathspec-from-file=/absolute/package/CHANGED-VS-PRIOR-SNAPSHOT.git-pathspec

git diff --cached --stat

git diff --cached --check

6. 自行檢查 diff 後再 commit。要 push 時先確認正確 private origin、branch 與最新遠端狀態；不可 force push，亦不可刪除或重寫既有版本。若遠端已移動或 private origin 無法核對就停止。本交接沒有替你 push、merge、接受新協議或啟動 provider。

不要把 top-level release ZIP、原始模型結果、權重、環境或認證檔一併加入 Git。先前的來源包與 notebook 版本均應保留。
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--release-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.release_root,a.out),sort_keys=True))

if __name__=='__main__':main()
