# NVARC 原配方重現：剩餘項目

日期：2026-10-01。依 [Decision 0050](../decisions/0050-separate-original-nvarc-reproduction.md)，
原版重現照收原配方與資料，透過獨立 materials/manifests/checkpoints/results
和 exposure 記錄隔離。此前五來源 filtered HF 是乾淨資料準備，不再用它的
排除條件阻擋原版重現。原輸出、舊契約及已消耗 run identities 保持不變。

後續依 [Decision 0051](../decisions/0051-run-qwen35-kaggle-gpu-preflight.md)
執行一次 Qwen3.5 Kaggle 資源檢查，詳見
[GPU preflight 001](../../trials/arc-agi-2-qwen35-nvarc/q35-gpu-preflight-001.md)。
四張 BF16 L4、來源 optimizer/loss 的一個全參數步驟及 checkpoint 恢復
fingerprint gate 通過。第二步的 9,330–11,196-token 完整序列在 backward
出現 cuBLAS 配置與 NCCL watchdog 錯誤，未完成第二 optimizer step。
001 的失敗與身份保持不變。

依 [Decision 0052](../decisions/0052-repair-qwen35-kaggle-gpu-preflight.md)
完成第二版修復與獨立 Kaggle 執行，詳見
[GPU preflight 002](../../trials/arc-agi-2-qwen35-nvarc/q35-gpu-preflight-002.md)。
CPU FP32 parameters/gradients/AdamW state offload、32 層 activation checkpoint
與 Gloo control/NCCL model groups 分離後，四張 BF16 L4 完成兩步、47,078
完整 input tokens，包含最長 11,196；checkpoint restart 通過。
長序列一步的 peak allocated 為 10.365–11.613 GiB，整本 notebook 約 32.38
分鐘。此特定 Qwen3.5 backend 的長序列資源 probe 已通過；完整 SFT gate
仍關閉，packing、全量 schedule 與原 Qwen3/NeMo parity 尚未完成。
兩版皆無 teacher、生成或評分；002 的 push、monitoring 與 retrieval 已消耗。

## 已具備與尚未具備

| 項目 | 現有證據 | 尚缺工作 |
| --- | --- | --- |
| 原 Qwen SFT 資料 | 原版六來源 3,255,481 records 與獨立 validation 720 records 已全量封存；HF 位元組與順序保留，逐列 compact projection accounting，input tokens 共 11,509,821,262，最長 11,196；雙親及 evaluation/dev exposure 保留，無篩選/截斷 | 原 Qwen3 tokenizer/NeMo preprocessor 數值 parity、實際 packing/attention isolation 對接；compact projection 計數不等於原 tokenizer parity |
| 新隔離與 corpus 契約 | 新 original-corpus-v1/contract、雙親 Arrow sidecar、validation split、獨立 materials/manifests/checkpoints/runs/results namespaces 與限定用途 reader 已實作；舊 clean-research/single-parent 契約未改 | 完整訓練及推論的 checkpoint/run/result 綁定待 backend 整合；material preparation 與 training/full-method readiness 保持分開 |
| Qwen SFT backend | 原 optimizer、token loss/schedule 有本機差分與分散式整合；002 的四-L4 CPU-state backend 完成兩步、47,078 完整 tokens 與 checkpoint restart，最長 11,196；tiny model/AdamW 每個 tensor 的連續與恢復路徑完全相同；舊八步 pilot export 仍獨立 | 六來源完整訓練、原 packing/attention isolation、12,716 steps/global batch 256 及匯出未完成；CPU offload 的全量資源與 throughput 未驗證；Qwen3.5 並非原 Qwen3 Megatron backend |
| Qwen TTT/推論 | tiny 真實模型完成 source r256/alpha32、128-view epoch、source context cut、DFS/rerank 差分；4B 有小步數 pilot | 4B 的完整 source TTT 與 8192 context 資源/耗時驗證；source batch KV/cache 與 throughput；完整候選搜尋、八視圖驗證、task reset 和 ranking 的目標 GPU 整合 |
| SDG 全流程 | 103,223 個已發表 pairs puzzles 已取得；source 十階段程式/prompts 和 bounded replay 存在；009 僅有五筆 two-template AST pairs | 若要重現生成過程：42,008,423,274-byte artifacts 包未取得；原 teacher/material bindings、十階段端到端、一般程式隔離、majority/filter/augmentation 對照未完成。使用已發表 pairs 做 SFT 不以重跑 teacher 為前提 |
| TRM | source 與 tiny CPU train/reload/TTT/inference/joint check 有證據 | published training/evaluation/checkpoint 包仍只有 metadata；原規模 GPU pretraining、EMA/checkpoints、TRM TTT/inference 與完整 Qwen+TRM 整合未完成 |
| 原版版本與權重 | source commit 固定；Qwen notebook v10、TRM notebook v21 已保存；Qwen3.5 compact 和八步 SFT export 已驗證 | 原 Qwen3-4B-Thinking-2507 compact base/原 ARC-SFT checkpoint 未取得驗證；TRM 原 v18 與已保存 v21 尚未建立 exact-version parity。Qwen3.5 是移植，不宣稱與原 Qwen3 權重或數值相同 |
| 目標資源與結果 | 001 的失敗診斷保持 frozen；002 使用同八筆完整資料，在四-L4/約 198.8 GB available host RAM 上完成兩步與恢復；長序列 peak allocated 10.365–11.613 GiB，CPU worker RSS snapshot 29.602–30.398 GiB/rank；29 個輸出 member digests 通過 | 已通過的 bounded unpacked probe 不等於全量 SFT；完整 recipe 的 packing、global batch、累積步數/tokens、CPU RAM/throughput、恢復耗時與匯出仍未驗證 |

資料的實際下載、digests 與 clean filtering 計數見
[資料報告](../../trials/arc-agi-2-qwen35-nvarc/dataset-acquisition-20261001.md)。
原版全量 corpus 的計數、隔離與證據見
[原版 corpus 報告](../../trials/arc-agi-2-qwen35-nvarc/original-corpus-20261001.md)。
未下載的資源身份與數量來自既有 `asset-inventory.json`；本次未另行查詢 provider。
原六個 training paths 和 validation path 以 pinned `ARChitects/sft_mg.yaml`
為準；原模型/steps/batch 以 `run_sft_4b.sh` 的有效 overrides 為準。

## 接續順序

1. 原重現 corpus/隔離契約和雙親 importer 已完成，六來源與原 validation 全量封存及獨立逐列驗證已通過；保留 proof，material preparation ready。
2. 補完整 source-recipe distributed SFT 與目標推論 backend，先做差分與資源
   preflight，再提出具體訓練執行包。
3. 補 TRM 材料與整合；若目標包含自行產生 SDG，再補 artifacts/teacher
   十階段。原模型、原 notebook version 的未重現差異逐項保留。

原資料準備變更完成本機原版 corpus importer/隔離及全量封存。該階段沒有
model/teacher execution、Kaggle 操作、scoring 或 paid work；strict backend
tests 只使用既有 synthetic/tiny CPU fixtures。後續 0051–0052 的兩次 GPU
probe 與已消耗執行身份依上方獨立紀錄保留。

資料準備時 repository `--all` 通過 302 tests（四個既有 optional skips）；新增五項
policy/real-HF checks 均通過。Strict ML 首輪 37/38，installed-wheel tiny model
因既有 60 秒 model-ready timeout 失敗，停止資料處理後單獨重跑通過，未改
timeout。完整首輪失敗及 recheck logs/digests 保留於原版 corpus 報告。

前次文件與 authority 更新後，repository `--all` 通過：299 tests、455.485 秒，
四個既有 optional skips。Log 保存在 ignored
`.irisx/nvarc-data/reproduction-direction-repository-001.log`。

第二版 GPU 修復的 repository `--all` 通過 306 tests（四個既有 optional
skips）；四項 focused checks 及加強後的兩項 strict tensor-resume checks
均通過。診斷 ZIP、安全隔離與 consumed-action guards 的本機驗證皆為零
external calls。Exact logs/digests 見 002 的 terminal record。
