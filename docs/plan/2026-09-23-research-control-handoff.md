# ARC 研究總控交接

日期：2026-09-23。Owner 最新指示：先 push 已完成工作，開啟下一個總控 task，
使用 **gpt-6-astra / high** 繼續討論後續研究。
本次只整合已完成實驗與交接；沒有新的 Kaggle、生成、反思或訓練授權。

## 角色與目標

- 新 task 是總控：分析證據、與 owner 討論研究、將計畫寫入 `docs/plan/`。
  實作與長時間實驗交給 owner 明確要求開啟的獨立開發 task。
- 總控模型 `gpt-6-astra / high`；開發與後續反思模型沿用
  `gpt-6-sol / xhigh`。反思使用 Codex CLI 方案使用量，記錄 elapsed；
  不自行改成 metered API 或額外付費 GPU。
- 長期追求 ARC-AGI-2 public evaluation 與競賽成績 85+，public evaluation
  是里程碑。現在的數字都是 public-training 的內部分割／診斷，不是官方分數。
- Owner 重視自己的 source、NVARC 與可追溯的開源程式／checkpoint／第三方或
  合成資料。重用成功實作和大型模型 Dataset，縮短 debugging、上傳與等待。
- GPU 時數目前沒有另設 owner 上限，但每個已授權 trial 的生成／時限／停止
  規則仍有效。不要把「GPU 時數不限」解釋成所有新研究已獲授權。
- 可將受 public-evaluation 污染的 checkpoint 用於競賽研發，但要明確標示
  public 分數受污染，並另保留乾淨基線。離線大規模訓練預算仍需另訂。

## 已完成的研究

1. Trial 001 已關閉，`inconclusive-no-promotion`，沒有可用準確率；不要重啟。
2. Trial 002 replacement smoke 在四張 L4 完成四次 Qwen3.5-4B inference，
   4 個有效 grid、0/4 exact match。它是 inference-only，未驗證 NVARC 適應。
3. DSPy/GEPA prompt pilot：256 train + 128 dev，另有 128 locked holdout。
   B1 train 18/256、dev 12/128；十次 proposal attempts、九個完成候選，
   沒有超過 B1，最佳候選 dev 10/128。所有 parent 都是 B1。當時反思是
   gpt-5.6-sol xhigh，歷史綁定不能改寫成 GPT-6。總共 3,840 次 Qwen 生成。
4. Decision 0020 budget ablation：固定 Qwen3.5-4B 和原 B1 instruction，
   在結果分層選出的 64 題 train 上，off/1024、off/4096、on/4096 各 64 次。
   三 arm 分別 18/64、18/64、7/64，cached off/512 為 18/64。
   沒有 arm 過門檻（淨增至少 4 題且保留至少 16/18），因此未跑後續 384 題。
   新生成合計 192 次；沒有任何 reflection/GEPA/TTT 呼叫。

## 最新判斷：已驗證的結果與限制

- 精確 tokenizer 顯示 384 個 train/dev 正解含 EOS 最多 930 tokens；28 題
  超過 512，零題超過 1,024。增加容量減少截斷，卻沒有增加正確答案。
- B0→A1：42 題 raw output 完全相同，22 題僅延長既有前綴。
  A1→A2：60 題完全相同，4 題延長無效輸出；沒有證據支持再擴純輸出上限。
- Thinking/4096 的 57/64 題沒有 final separator 就用完總 token 預算。
  其餘七題有 final 且全對，但不能排除 57 題失敗而報 100% 準確率。
  這只測 greedy + B1 prompt + 共用 4096 上限，不是模型無限制能力上限。
- 四卡 session 約 78.87 分鐘，四個 worker 各只載入模型一次、都正常派工。
  Thinking 佔總生成工作時間 81.6%；這次主要等待不是上傳或 GPU 沒有排程。
- 重要校正：舊 holdout 的 `runtime competition case differs: f3e62deb`
  不是來源漂移。完整 512 題 visible source 一致；舊 gate 把第一個 test input
  視圖與包含兩個 test inputs 的整題比較。Holdout 沒有預測與分數，不能填零。
- 64 題診斷集刻意依既有成功／失敗分層，不能外推準確率；dev 亦已被多輪
  選擇使用。未來須區分 task-level、test-index-0 與完整官方評分分母。
- 開發 head `e8868c6` 的 156 tests 通過；總控獨立重算 score/cohort/source
  audit/qualification 和 raw-output exact match 均一致。程式與結果紀錄已
  整合 main，凍結 result/outbound/ledger 保持原樣。

## 接下來討論什麼

總控建議暫停同類 prompt/token sweep，主線回到 NVARC/ARC-trained checkpoint。
先查現有 source、可取得 checkpoint、資料曝光、模型與 tokenizer 相容性，
再設計小型的相同 checkpoint、task-local adaptation 關／開對照。

NVARC 原 ARChitects 是 Qwen3 4B、專用 tokenizer/16 embeddings 與 SFT；
不能把通用 Qwen3.5-4B 加一段 LoRA 就叫作完成 reproduction。是否先復現原
checkpoint 路線，或承擔 Qwen3.5 移植／訓練成本，是尚待討論的研究選擇。
不得假設 checkpoint 沒看過我們的 train/dev 或 public evaluation。

Thinking 保留為可選的小型支線：若再研究，先量測可控時限內交付 final 的能力，
不要直接把整批題目升到 32K。新的 GEPA 必須有 failure type、stop reason、
token usage、成功案例保留與 request/案例 coverage 紀錄。
這些都是討論方向，不是自動開始新實驗的指令。

## 讀取順序與實體證據

先讀 AGENTS.md，再讀：

- `trials/arc-agi-2-budget-ablation/control-review.md` 和同目錄 README。
- `trials/arc-agi-2-prompt-pilot/control-review.md`、`failure-analysis.md`。
- `docs/plan/2026-09-23-arc-reasoning-budget-ablation.md`（已完成設計）。
- `docs/plan/2026-09-22-arc-agi-2-completable-baseline.md`（source 與 NVARC 沿革）。
- Decisions 0019、0020 僅在核對歷史範圍時讀取；其工作流程都已終止，
  剩餘 ceiling 不是新的執行授權。

Ignored evidence 不會隨新 task/worktree 或 Git push 自動複製，使用下列實體路徑：

- Prompt pilot：`C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot/`。
  `repair-002/recovered-v1/result.zip` 是 B1；`search/` 有候選、score、ledger。
- Budget ablation：`C:/Users/wurre/.codex/worktrees/918a/IRIS-X/.irisx/arc-agi-2/budget-ablation/`。
  `ledger.json`、`analysis.json`、`cohort.json`、`diagnostic/score.json`、
  `diagnostic/retrieved/result.zip`、`source/visible-audit.json`；
  `source/tokenizer/` 有精確 tokenizer，`source/competition/` 有官方 challenge。
- 總控額外核對：`C:/Users/wurre/Desktop/IRIS-X/.irisx/budget-ablation-review/`，
  包含 `review.py/json` 和 `token_check.py`、`token-check.json`。
- 新 result SHA-256：`65e2d694e7268815d1b7d594218dea2012c1a7694d108048c1cb543f878edeea`。

唯讀使用舊 evidence 或選擇性複製並驗證 digest；不要改寫、刪除舊 worktree。
多數 JSON 是很長的單行，應解析後只輸出需要的欄位，不要直接整檔印出。
必要時先找現有資料，避免把 source inventory 誤當成要重建已刪除的 legacy roots。

任何後續 Kaggle 設計必須掛載官方 `arc-prize-2026-arc-agi-2`，private、
Internet disabled、`NvidiaL4`，實測四個不同 L4 與四卡動態排程；沿用成功
runtime/model Dataset，先做 source parity、明確分母與本機測試再提交。
