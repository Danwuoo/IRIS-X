# NVARC 原配方重現：剩餘項目

日期：2026-10-01。依 [Decision 0050](../decisions/0050-separate-original-nvarc-reproduction.md)，
原版重現照收原配方與資料，透過獨立 materials/manifests/checkpoints/results
和 exposure 記錄隔離。此前五來源 filtered HF 是乾淨資料準備，不再用它的
排除條件阻擋原版重現。原輸出、舊契約及已消耗 run identities 保持不變。

## 已具備與尚未具備

| 項目 | 現有證據 | 尚缺工作 |
| --- | --- | --- |
| 原 Qwen SFT 資料 | 固定第 1 版 augmented 和 synthetic ZIP 已完整取得及 SHA/CRC 驗證；六個 training sources 共 3,255,481 records；另有 720 筆原 validation source | 對未篩選的全部來源做格式/token accounting、原始 loader/packing 對接與正式 corpus freeze；保留 evaluation/dev exposure 與雙親 lineage，不套用乾淨分支的排除和 8192 review cap |
| 新隔離與 corpus 契約 | raw ZIP 與 clean filtered HF 已分開，雙親索引已建立 | 現有 freezer 只接受 clean-research 和單親 parent_id；補原重現 policy、parent_ids、validation split、隔離 namespaces 及 readiness 判定；舊契約不覆寫 |
| Qwen SFT backend | 原 run_sft_4b.sh/YAML 的 optimizer、loss/schedule reference 有本機差分；4-L4 pilot 有八步、2,578-token export | 六來源 distributed loss normalization、原 packing/attention isolation、optimizer/scheduler/checkpoint/resume 完整整合；原 12,716 steps/global batch 256 的完整訓練及匯出未完成；Qwen3.5 hybrid backend 並非原 Qwen3 Megatron backend |
| Qwen TTT/推論 | tiny 真實模型完成 source r256/alpha32、128-view epoch、source context cut、DFS/rerank 差分；4B 有小步數 pilot | 4B 的完整 source TTT 與 8192 context 資源/耗時驗證；source batch KV/cache 與 throughput；完整候選搜尋、八視圖驗證、task reset 和 ranking 的目標 GPU 整合 |
| SDG 全流程 | 103,223 個已發表 pairs puzzles 已取得；source 十階段程式/prompts 和 bounded replay 存在；009 僅有五筆 two-template AST pairs | 若要重現生成過程：42,008,423,274-byte artifacts 包未取得；原 teacher/material bindings、十階段端到端、一般程式隔離、majority/filter/augmentation 對照未完成。使用已發表 pairs 做 SFT 不以重跑 teacher 為前提 |
| TRM | source 與 tiny CPU train/reload/TTT/inference/joint check 有證據 | published training/evaluation/checkpoint 包仍只有 metadata；原規模 GPU pretraining、EMA/checkpoints、TRM TTT/inference 與完整 Qwen+TRM 整合未完成 |
| 原版版本與權重 | source commit 固定；Qwen notebook v10、TRM notebook v21 已保存；Qwen3.5 compact 和八步 SFT export 已驗證 | 原 Qwen3-4B-Thinking-2507 compact base/原 ARC-SFT checkpoint 未取得驗證；TRM 原 v18 與已保存 v21 尚未建立 exact-version parity。Qwen3.5 是移植，不宣稱與原 Qwen3 權重或數值相同 |
| 目標資源與結果 | 過去 bounded 4B pilots 和本機 tests 有證據 | 對完整 recipe 固定硬體、記憶體/磁碟、步數/tokens、wall time/checkpoint/恢復；取得完整執行結果，按 exposure 報告，並把原版結果與移植品質分開 |

資料的實際下載、digests 與 clean filtering 計數見
[資料報告](../../trials/arc-agi-2-qwen35-nvarc/dataset-acquisition-20261001.md)。
未下載的資源身份與數量來自既有 `asset-inventory.json`；本次未另行查詢 provider。
原六個 training paths 和 validation path 以 pinned `ARChitects/sft_mg.yaml`
為準；原模型/steps/batch 以 `run_sft_4b.sh` 的有效 overrides 為準。

## 接續順序

1. 補原重現 corpus/隔離契約和雙親 importer，凍結全部六來源與原 validation。
2. 補完整 source-recipe distributed SFT 與目標推論 backend，先做差分與資源
   preflight，再提出具體訓練執行包。
3. 補 TRM 材料與整合；若目標包含自行產生 SDG，再補 artifacts/teacher
   十階段。原模型、原 notebook version 的未重現差異逐項保留。

本次變更只整理原版重現方向與缺口。沒有新下載、model/teacher execution、
Kaggle 操作、scoring 或 paid work。

本次文件與 authority 更新後，repository `--all` 通過：299 tests、455.485 秒，
四個既有 optional skips。Log 保存在 ignored
`.irisx/nvarc-data/reproduction-direction-repository-001.log`。
