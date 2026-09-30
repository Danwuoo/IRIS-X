# NVARC 方法完整性：先補方法，再比較品質

日期：2026-09-30。Owner 授權接續三個開發順序；本次採 routine lane，
在 main 做本機、離線、可逆開發。沒有新的 Kaggle save/run、Dataset mutation、
retrieval、teacher invocation、付費執行或 locked/hidden scoring 授權。

## 1. 版本、分支與方法邊界

檢查起點為 main `9033d6736d3d9559d88b69a40be0de6577a6f333`。
51fa 開發 worktree 的 `00db35` 已透過 `f30baa8` 合入 main；c1e4 的
`26742ab` 也已合入。NVARC archive snapshot `8511736` 與 main 的
`81b5289` patch 等價。沒有遺失的 NVARC 開發內容需要再 merge。
封存 chat 與 worktree 的 Git 狀態分開查核；本次沒有重複 merge 或 push。

[ABC 005 的完整診斷](../../trials/arc-agi-2-qwen35-nvarc/compact-abc-005-editor-diagnosis.md)
已完成，A/AT 各 1/3、B/C 各 0/3。這是三個反覆使用的公開開發題，
且 B 是八步、2,578 input-token 的工程 SFT pilot；它不足以驗證完整
NVARC 訓練的效益。暫停從這個 checkpoint 接續 ABC 006 調參。

[方法契約](../../trials/arc-agi-2-qwen35-nvarc/configs/method-contract-20260930.json)
把三條路徑分開：Qwen4B-only、SDG、Qwen3.5+TRM。它固定來源 commit、
Qwen notebook v10、可取得的 TRM notebook v21、原始有效配方與移植差異。
TRM v18、原 Qwen3 權重/規模/成績，以及 Unsloth/Megatron 的數值與效能
一致性，都沒有被宣告完成。SDG 的五筆 two-template AST pairs 不代表
完整十階段或任意 Python sandbox 的 teacher yield。

## 2. 補實作並驗證訓練語意

| 部分 | 新實作與驗證 | 尚待完成 |
| --- | --- | --- |
| 六來源 SFT | 透過真正的上游 HF loader 串流讀取 arc2_training、mini、concept、rearc、nvarc_training、nvarc_full；閉合檔案 inventory、逐筆 parent lineage、來源 counts、開發題排除與 token accounting；保存 source spec 和 indexed JSONL shards | 實際六來源資料與可信 exposure/lineage 尚未取得；fixture 永遠不能令 data readiness 成立；未知 semantic overlap 仍需查核 |
| SFT reference | 有效 run_sft_4b.sh/YAML 配方離線解析並比對契約；AdamW betas/epsilon、非零 floor 的 linear warmup/decay、按 supervised-token 加權的 gradient accumulation | single-process、unpacked reference；現有 bounded FSDP pilot 尚未移植此六來源配方；packed DeltaNet 隔離與 GPU 資源量測未完成 |
| TTT | opt-in source-one-epoch；原始 n=16 augmentation 的 128 views 全部消耗一次；r256/alpha32 rsLoRA、cosine/warmup、梯度裁切、預先 step/token gate 與 task reset | tiny 真實 hybrid 模型已驗證；4B r256/8192-context 的記憶體、耗時與品質未量測；seeded randperm 不宣稱等於 Trainer sampler |
| Context | 呼叫來源 cut_to_len，以完整 demo 為裁切單位；8192 context 保留 931 reply tokens；無 reply 至少保留一個 demo，避免來源 get() 的空 challenge 錯誤 | 極端不可容納的 query/demo 明確拒絕，不做逐 token 截斷 |
| DFS / rerank | 沿用來源 traversal/pruning/ranking 差分測試；新 tiny 模型檢查裁切後的多 test generation 與八視圖 summed answer-NLL | full-prefix correctness reference；來源 shared batch KV/cache 及 GPU throughput 未重現 |
| SDG / TRM | 保留既有來源差分、真實 namespace replay、tiny TRM train/reload/TTT/joint verification 回歸 | 不把 bounded AST teacher observation 升格為一般 SDG；完整資料、目標規模訓練與 joint GPU 執行仍缺 |

歷史 pilot 的預設 training/candidate 行為保持原樣；新排程與 context 是
顯式 opt-in。所有已保存/執行的 notebook、plan、checkpoint、result identities
保持凍結。新程式不讓 routine 開發轉成 external execution authority。

ABC 001～005 的歷史 preflight 增加明確的 `retained_review` 模式，依各
tracked status page 的確切 wheel SHA-256 查核原封裝，不要求凍結原碼跟著
main 開發變動。預設 preflight 仍逐檔比對當前原碼；歷史模式不宣告
`wheel_matches_source`，且所有 report 的 `execution_authorized` 為 false。
沒有重建、修改或覆寫任何已消耗的 package/preflight/result bytes。

嚴格測試會真的更新 tiny Qwen3.5/PEFT 權重：完整 128-view r256 epoch、
四類 LoRA gradient、精確 reset、與獨立 per-token cross-entropy oracle 比對
的 variable-length accumulation，以及 continuous/resumed SFT 權重相等。
來源裁切及八視圖 NLL 也有原 notebook oracle；重算 hash 的壞 loss mask、
排除 parent、shard tampering 必須拒絕。這些是本機方法 reference 證據，
沒有新 4B 或 teacher 訓練結果。

## 3. 前提成立後才啟動新訓練與比較

`tools/nvarc_method.py` 的 audit 不以八步 export 滿足 full-SFT gate。
本機 proof 綁定方法契約、當前程式 hashes 和成功 test log；失配即拒絕。
即使六來源 inventory/declared lineage 與本機 proof 都成立，report 也只表示
bounded-training 的資料/reference 前提成立，並不授權執行或表示 GPU 方法完成。

已可產生 inert `nvarc-source-method-dev-proposal-001`：compact base、**新**
六來源 SFT checkpoint、相同新 checkpoint 加完整 source-epoch TTT。
固定選八個公開 training development parents，排除原十六個 pilot parents；
實際 corpus 存在時再排除其 training parents。只輸出 demonstrations 和 test
inputs，所有 test outputs 留在原來源/evaluator，不帶進 solver artifact。
多 test cases 完整保留；比較 task 與 per-test exact match、top-two coverage、
missing/invalid 和成本。三臂最多 384 個 task-shared generation calls 的數字
只是待審候選預算，沒有 save/run allowance。

先產生 provisional dev manifest，再在真正資料 freeze 時排除這些 parents，
最後重建 comparison 並比對 split，避免完整 arc2_training 與 dev 重疊。
更廣的已發表 SDG exposure 尚未查核；這組新題也不稱為 fresh holdout。
SFT 的 steps/tokens/batch、記憶體、時間與 session bounds 必須依實際 corpus
及 backend 量測後固定；不能把原 12,716 steps 或八步 pilot 直接當成新 budget。

目前六來源材料缺失，proposal 應為 `inert-materials-blocked`，品質 gate
維持 false。下一段本機開發為分散式 source-recipe 的 token normalization /
optimizer/scheduler/resume 差分，以及已有原始公開來源的 lineage builder。
材料取得和目標 GPU 執行需要另外綁定具體資料、範圍及預算；在此前持續做
本機實作，不啟動新的 ABC 調參。

## 本機入口與查核

參閱[更新 runbook](../../trials/arc-agi-2-qwen35-nvarc/runbook.md)。
實測 logs、proof、readiness 和 proposal 保留在 ignored `.irisx/`；耐久的
方法、限制與完成狀態在本文件、trial README 和 reproduction matrix。
Repository check 與 strict ML profile 必須在交付前通過，實際測試結果
在 trial README 記錄。這份文件不是新的 execution decision。

2026-10-01（台北）交付查核：

- strict ML profile：38 tests / 396.020 秒 / 零 skip，通過。
- repository `--all`：293 tests / 329.212 秒 / 四個既有 optional skips，通過。
- 新方法 acceptance：四項真實 tiny-model/source differential checks 通過；
  歷史 ABC 檢查十六項通過；預設 current-source preflight 仍拒絕舊 wheel。
- readiness：`source_ready=true`、`local_reference_verified=true`、
  `corpus_ready=false`、`quality_comparison_ready=false`。
- 比較草案：八個 parents、九個完整 test inputs，獨立比對原來源證實僅
  test outputs 被移除；與既有十六題互斥；失配 code binding 的 proof 被拒絕。

本機 artifacts 位於 `.irisx/arc-agi-2/qwen35-nvarc/method-reference-20260930/`。
契約 digest 為
`sha256:7b1fdc11e10798c95b14aca7b7e396b61662365f7db5ef68440ccba7ab2570d9`。
SHA-256 bindings：

| Artifact | SHA-256 |
| --- | --- |
| `proof.json` | `8082578330c8c23ef7b8358f7a4d745cc996ea6b6928e9be66fef113a40808d8` |
| `strict-ml.log` | `997c946ed861c0be220c269d3d86c42aa4dda618567c1dea2c291114603445fb` |
| `readiness.json` | `78d205e5e58dbb51ff3f2602a6bd5e15098e696514456ec5043985f91142a2d2` |
| `comparison-review-001/proposal.json` | `28e182b106a1f3c1ace8d88da729400a7fffb4aa720f73cdd3a02f4fe0017f17` |
| `comparison-review-001/dev-visible.json` | `bc91105466ba9bcf152f3c60c74ec098804d9833c5d6a33d2451a0e2dfb8f34b` |
| `.irisx/nvarc-method-repository-final-20260930.log` | `bd6951f58ee4ca196d4cec3acc0ebd472f95b16aabcc8e255b74ea9944a5bb68` |

Provisional parents：`337b420f`、`73ccf9c2`、`c0f76784`、`c4d1a9ae`、
`cf5fd0ad`、`d23f8c26`、`e1baa8a4`、`f3cdc58f`。這是 pending training-data
exclusion 的公開 development manifest，沒有 locked-holdout 或 solver 分數。
