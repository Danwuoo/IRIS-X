# NVARC M2–M3 開發與小型執行界線

日期：2026-09-24。Owner 本次要求 source-integration 計畫的 M2 真實 ARC-SFT
與 M3 SDG/TRM 開發和本機小型驗證；不涵蓋 M4 四 worker benchmark。
主線直接在 main，沿用固定來源、compact 4B 與既有 source stage；所有新輸出
在 `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`，舊執行身份不修改。

## 本機流程

1. 從固定 `ARC-AGI-2@f3283f7` 公開 `data/training/` 挑選 16 個具體 parent，
   凍結逐檔 SHA-256、8 train/8 dev、序列上限、augmentation seed、步數及 token
   ceiling。只有 train parents 產生 16 個 source augmentation views；dev 僅
   以無標籤 visible test 做推論。排除 `arc2_evaluation6`、evaluation/holdout
   與任何來源不明的衍生資料。資料輸出及 checkpoint 列出 exposure。
2. 先對 tiny **實際 Qwen3.5** 做完整參數、unpacked SFT，驗證梯度與權重
   有限、step/cursor/RNG/optimizer 的續訓一致，以及 checkpoint export/reload。
   用新 export digest 餵入現有 source TTT → bounded DFS → inverse/dedupe →
   source ranking，留下 truth-free result 和各階段 wall/tokens/forwards/memory。
   4B full-SFT 另需實測能容納參數、gradient、optimizer 的 backend；DDP
   不視為分片方案，NeMo/Megatron Qwen3.5 支援未證明前不得宣稱可執行。
3. SDG 先對固定上游 prompts/十階段做 saved-response replay。generated Python
   只可進真實容器 sandbox；逐項實測 timeout、memory/process、filesystem/network
   拒絕、pair/filter。若 daemon 缺失，保留可直接啟動的 pinned image 方案及
   未執行狀態，絕不在 host 上執行生成程式。
4. TRM 使用 pinned upstream builder/model/loss/train 與 NVARC 設定，先在 CPU
   少步訓練真實模型、save/reload、題內 TTT、visible-only inference；checkpoint
   記錄 train parent exposure。再把真正 TRM candidate 接 Qwen verifier，保留
   branch、counts、缺候選及每個 artifact digest。發表的 checkpoint 若另用於
   接線，不能取代這次訓練或當 clean dev 分數。

## 外部執行預備與停點

固定 package 必須有 model/data/runtime/source digests、precise calls/tokens/
steps/deadline、預期輸出、私有留存與 truth-free gate。Kaggle 目標為免費、
private、Internet-off、USD paid 0。先做本機 preflight 與計算資源估算，然後
依 `AGENTS.md` 和 `docs/development/data-and-execution-policy.md`，只就精確
Kaggle Dataset/kernel/取回上限及 SDG teacher provider/model/calls/tokens/USD
上限向 owner 一次提出整合請求。現有四 kernel/八 GPU 小時只是舊提案，
Decision 0027 已消耗；本文件不啟動 provider 執行。

小批工程可執行不等於 ARC 能力提升、原 NVARC 規模重現、holdout 評分或 M4
完成。任何實際缺口及失敗留在 trial status 和 reproduction matrix。
