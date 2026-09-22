# Trial 002 Kaggle 修復與四次推論 smoke

日期：2026-09-22

狀態：owner 已要求開新 task 修復；由新的 GPT-5.6 Sol / xhigh task 執行。
本計畫是 [原基線計畫](2026-09-22-arc-agi-2-completable-baseline.md) 的本輪修復範圍，
衝突時以本次明確指令為準；Trial 001 保持關閉。

## 問題與已確認事實

Owner 回報舊 task 宣稱 notebook 成功啟動，但 notebook 失敗、未掛載
ARC-AGI-2 競賽資料、未設定 L4 x4。本總控已確認：

- 舊 task：`01a0c701-e6ed-7d30-bef4-a2cac78e53ec`，
  名稱「開發 ARC-AGI-2 可完成基線與 NVARC 適配」。
- 舊 worktree：`C:\Users\wurre\.codex\worktrees\543a\IRIS-X`；
  HEAD `7fb10a7c8c8795839d7b815dce0dc91042f50d0e`，實作有 19 個未提交檔案。
- 追蹤模板及 local kernel staging 都有 `competition_sources: []`。
- metadata 寫 `machine_shape: NvidiaL4`，不等於伺服器配置已被接受，
  也不證明 runtime 有四張 L4。
- 舊回覆稱 kernel version 1 啟動；確切 kernel ID 不能只按模板猜測：
  回覆使用 `danielwuu/iris-x-arc-agi-2-trial-002-smoke-001`，
  檔案則為 `danielwuu/irisx-arc-agi-2-trial-002-smoke-001`。
  必須核對提交 receipt 與伺服器端版本，避免抓錯 notebook。
- 尚未在總控驗證完整 traceback，修復 task 必須取得失敗版本輸出診斷。
- 舊取回 automation `retrieve-trial-002-smoke-once` 已不在本機 automation
  檔案清單；不可假定它會替新 task 取回結果，也不要重建它喚醒舊 task。

## 精簡交接，保留未提交實作

新 task 從專案獨立 worktree 開始；不要 fork 滿載對話。
19 個檔案已逐檔複製到本機唯讀交接來源：

```text
C:\Users\wurre\Desktop\IRIS-X\.irisx\control-handoffs\trial-002-smoke-repair-20260922\
  manifest.json
  files\...
```

先驗證 manifest 的每個 SHA-256，再將 files 內列明的檔案納入新 worktree。
此為未審核完畢的實作起點，不是通過 runtime 的成果。不得整包拷貝 credentials、
舊虛擬環境或 models 到 Git，也不重設／清理／提交舊 worktree。
原 `.irisx/arc-agi-2/trial-002/` 內 model、NVARC checkout、wheelhouse、
outbound 和執行 evidence 可唯讀複用；新的生成檔案另放新 run 目錄。

## 本輪固定範圍

- 模型固定 `Qwen/Qwen3.5-4B`，沿用並驗證 revision
  `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`，不重新選模型。
- 目標 GPU 是真實 L4 x4，不容許 T4、CPU 或單 L4 靜默 fallback。
- 必須掛載當屆 ARC-AGI-2 競賽來源；先核對 competition slug
  `arc-prize-2026-arc-agi-2` 是否為 owner 使用的當屆競賽。
- 本輪是 **總共四次實際生成 invocation**，不是四題乘上 attempts、views、
  beams 或候選數。採四個不同 task 各一個 test input、一次生成，固定 seed
  與來源清單；一張卡一個 job。使用既有四個 task ID 時先確認它們存在於
  實際掛載的 challenge 檔。找不到即報錯，不退回假資料或未掛載來源。
- 每次 invocation 只回傳一個 sequence，禁止隱藏 warm-up generate、
  多視角生成、beam 多候選、修正迴圈或失敗後額外 model retry。
- 這是縮小的 inference-only 診斷，本輪不做 TTT/SFT/RL；保留 NVARC
  適配程式與後續設定，不以關閉適應宣稱完整 NVARC reproduction。
- 沿用單次 session 總上限 3,600 秒，每個 job 最多 300 秒，預留收尾，
  USD 0 外部付費。此次 owner 修復要求授權一個新的修復 smoke；不是重用
  舊 run 授權。新 run ID 建議 `trial-002-smoke-002`，不同 bytes 不覆寫 001。
- 四次 smoke 不做 pass@2 或整套 ARC 品質聲明；若每題只有一個輸出，
  不複製 grid 冒充第二個 prediction，不更動完整 evaluator 語義。

## 修復工作與證据

1. 取得失敗 kernel 版本的 metadata、notebook 與可用 logs/traceback，保存
   原始版本與錯誤。這是已失敗 run 的診斷，不是監控正在運算的 job。
2. 找出確切失敗原因；同時檢查資料掛載、GPU entitlement、模型/wheel 相容性、
   outbound 重建和 package digest，不只修 metadata 表面文字。
3. 使用安裝版 Kaggle CLI/API 所支持的正確欄位與 accelerator request。
   不從其他 notebook 的 `NvidiaL4` 名稱推斷 L4 x4；驗證送出的請求及
   伺服器保存的設定。保留必要 CLI version、request/receipt，隱去 secrets。
4. `competition_sources` 必須有真實競賽 slug，模型/依賴 Dataset 也要保留。
   啟動前檢查 expected mount 與 challenge JSON 存在，按允許清單讀取
   challenge/demonstration/test-input；solver 不讀 solutions/test truth。
   競賽掛載可能包含答案檔，不能因此宣稱物理上無答案；證據應精確說明
   solver 的允許輸入與實際讀取界線。若掛載資料與 pinned 官方 snapshot
   不同，記錄實際來源和 digest，不能冒充舊 commit。
5. 在 **任何模型工作前** 記錄 `torch.cuda.device_count()`、每卡名稱、memory、
   device ID 及相關 `nvidia-smi` evidence；必須證明四張 L4，否則 fail fast。
6. 全域 invocation quota 綁定 run/checkpoint，四卡共享計數與唯一 job keys。
   每次 generate 前記錄 started、完成後 terminal；failures 不能被當成
   completed inference，resume 不可增加第五次，也不可重跑已 consumed invocation。
7. 保存各次 raw completion（有大小上限）、grid parsing 結果、duration、token
   數、停止原因及 exception。無有效 grid 可記模型輸出格式失敗，不能稱 solver 成功。
8. 本機測試覆蓋實際將提交的 notebook/metadata/staging build，而非只測
   runner helper：competition 未掛載、GPU count/model 錯誤、CLI shape 未接受、
   被忽略的 metadata key、超過四次生成、stale wheel/runner/hash 均應被檢出。
9. 完成離線測試、artifact binding、技術 preflight 後用已授權 CLI 提交新版本。
   measured Internet 關閉；可使用既有 Kaggle 認證，不列印 token；不 publish
   public notebook、不送 competition leaderboard、不改用付費資源。
10. 完成後下載確切版本結果、quarantine 驗證、更新 Trial 002 README 與必要
    新授權記錄，跑 repo validation 並 commit；不自行 merge/push。

## 成功聲明與等待規則

- CLI push 成功：只能說「平台已接受提交」，不能說模型已成功啟動。
- runtime-started：必須有資料掛載、四張 L4 與模型載入/開始事件證據。
- inference-smoke-complete：四次真正生成都完成，結果已下載並通過身分驗證；
  另列有效 grid 數，不能用 fallback 或四個 timeout 宣稱成功。
- 如果只是排隊、preflight fail、worker crash 或缺失輸出，使用對應狀態。

延續 owner 的「中途不監控」要求：提交後不反覆輪詢、不串流 logs。
可檢查保存的靜態 metadata/提交 receipt，但不把它當 runtime 成功證據。
完成通知或預定執行窗口後做一次終態檢查與結果下載；若仍未結束，明確回報，
不可偽造完成或改成輪詢。需要延後取回時建立綁定 **新 task、新 kernel/version**
的一次安排，核對 Asia/Taipei 與 UTC 實際觸發時間，不複用舊 task 排程。

交付報告至少包含：traceback 根因、修復差異、已保存的 competition/GPU 設定、
實際 GPU evidence、四次 invocation 明細、kernel/version、結果路徑/digest、
測試與 commit、任何尚未完成的部分。缺哪項就如實標示。

```powershell
python tools\repository_check.py --all
```
