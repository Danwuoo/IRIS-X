# 後續訓練計畫（重新整理的提案）

更新：2026-10-09。本文件由既有研究、仍在 main 的資料驗收與先前討論重新整理，使用新的檔案／commit 身分；不是遺失檔案的逐位元恢復。當前 calibration 已回報失敗，先修復及驗證原 pilot，再決定下列實驗；本文不啟動新訓練、付費資源或官方提交。

## 基線與限制

目前 trainer 的 profiles 為 smoke2、pilot16、pilot128，沒有可直接延長訓練的 checkpoint/resume。pilot128 是 optimizer updates 目標，不是已完成的事實。單一 notebook 啟動流程執行訓練、固定 NLL 與匯出，不會自動完成 A/B/C 解題比較。

仍可核對的 `validation/public-training-readiness.json` 顯示：首輪選 32 training／4 development task groups。Granite 的 4096-token 全 row 排除後，training 剩 90/107 LODO rows、27/32 groups；development 剩 12/16 rows、3/4 groups。選定的 pre/post NLL 僅有 4 rows、2 groups、68 supervised tokens，不能據此宣稱一般化或 ARC 解題提升。

## 建議的四輪

1. **先完成相容性，再做解題比較。** 修補後取得完整 run 證據，確認實際 updates、tokens、時間、峰值記憶體、cleanup 及 adapter 匯出／重載。用同一 pinned Granite base 與 adapter，比較 A direct-grid、B program proposal、C execution-feedback repair。先用既有四題確認完整分母與輸出，再預先凍結 32 個 development groups、兩個 seeds 的比較。主要看 top-2、候選池 oracle 及實際 GPU 時間；NLL 只是輔助。

2. **Granite 擴充資料與學習曲線。** training groups 由 32 擴至 128，所有 augmentation 和 synthetic descendants 跟隨來源 task／generator family 分組，避免洩漏。維持 BF16＋LoRA，先量資料覆蓋，再比較實際 tokens／GPU 時間下的逐級 checkpoints。另測 8192-token 完整長題，不截掉答案；仍超長者如實列出。長訓練前須實作與驗證 optimizer、RNG、data cursor 的 checkpoint/resume 和 fresh-process reload。

3. **Qwen、Seed 做短程對照。** 依序 Qwen3.5-9B、Seed-Coder-8B-Reasoning，固定 task groups、訓練目標和評測，分別比較相同資料曝光、相同 GPU 時間，另報各自原生 tokens。同 token 上限不等於相同 FLOPs。選擇依可重現解題增益、完整執行成本和 L4 可部署性，避免一開始讓三個模型都長訓練。

4. **有有效程式後再做 trajectory SFT。** 使用 training-only、可重播的 proposal、真實 executor 錯誤與 repair targets，混合 grid-retention，並與等預算 grid-only SFT 對照。Tool feedback 不計 assistant loss；demonstration-fit 不冒充 test 真值；development／confirmation 成功 trace 不回流訓練。語法或介面失敗主導時可做小型合成課程；合法程式仍無正解時，先查表示法與資料，不直接上 RL。

## 決策與部署

完整分母、真值隔離、來源可重播是先決條件。匹配成本下，跨 seeds 出現可重現新增解題且 top-2 不退步，才列入擴大候選。只有 oracle 上升而 top-2 不升時先研究選擇器；C 同成本輸給獨立提案時減少修復深度。只有 NLL 降低不能成為延長訓練的理由。

進入長訓練前，先完成單張 L4 匯出重載、最長輸入及峰值記憶體測試，再驗四張獨立 replicas。4×24 GB 不是任意單模型可用的 96 GB。RL、router、全參數微調與完整 NeMo 遷移後置；效率工具須另外驗證 attention、positions、labels，Qwen 另需 recurrent-state 隔離。

## 預算與保留資料

先用小 screen 的實測吞吐和時間，決定是否要跑完整 base/adapter × A/B/C × 多 seeds 矩陣及如何分批。不得沿用 1800 秒總上限，卻把只先完成的子集當作完整結果。程式時間上限也不是 VM 計費上限。GPU 小時和金額須在測得耗時、tokens、峰值與重載之後估算。

既有 locked confirmation 保留至最後的凍結比較，不進本輪訓練或開發選擇。公開來源的模型 pretraining exposure 仍未知。本計畫沒有足以承諾官方分數超過 85 的證據。

## 可核對的既有檔案

- `research/arc-next-line/architecture-memo.zh-TW.md`
- `research/arc-next-line/model-hardware-memo.md`
- `research/arc-next-line/model-source-lock.json`
- `research/arc-next-line/validation/public-training-readiness.json`
- 新整合後的 `tools/arc_next_training.py`、`tools/arc_next_workflow.py`、`tools/arc_next_offline_runtime.py`
