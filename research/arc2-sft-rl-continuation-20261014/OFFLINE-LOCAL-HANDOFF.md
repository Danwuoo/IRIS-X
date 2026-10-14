# 離線續接工具交接

日期：2026-10-14 UTC。研究基準固定為
`cc14bd1a79aac1fe6135017c9e09d4834300675d`；工作分支為
`feat/arc2-sft-rl-continuation-20261014`。

工具版本、開發任務、驗收證據與下一步統一見
[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)。本頁只維護使用方式與限制；
取得來源時須確認精確 commit 包含所需模組，不能以 Stage 0 的 SHA 指稱後續整合。

## 交付範圍

此 companion 提供既有 SFT256 → RL／等成本額外 SFT 比較的離線準備與結果解讀。
它不執行訓練、不提交或監看 Kaggle、不重跑 scorer，也不重建原始私人 admission。
本地 executor 的執行／提交責任與登入分開；沒有 credentials、帳號設定、
原始 evaluator 答案或私有執行封包隨此工具移轉。

CPU 元件、保存的 log-probability 與宣告性 metadata 不能代替真實模型 replay、LoRA
梯度、儲存／重載、整段成本或 GPU 實證。工具使用不改寫 run008 的凍結比較。

## 取得與核對

使用此分支中經遠端核對的 commit，保存完整 SHA；不要以日後移動的分支名稱
替代執行來源身分。一般公開 Git checkout 即包含必要來源，無須取得 Drive
封包或帳號設定。保留 run008、main 與工程重整線，不混入它們的新變更。

Stage 0 的 `prepare`／`analyze` 只需 Python 標準函式庫及支援 descriptor-relative、
`O_NOFOLLOW`／`O_DIRECTORY` 的 POSIX API。Windows 等不支援環境會明確拒絕
檔案操作，應交給支援的本地 POSIX 環境；不要停用安全檢查。Python版本與
檔案系統仍須在接收端測試，此機器的實際路徑不能直接照搬。

獨立 opt-in 的 audit-loss 入口另需 AF3 bridge、Pydantic 與 PyTorch；不得由 Stage 0
命令暗中載入。依賴與 CPU proof 環境見 [AF3 使用說明](../../tools/arc2_agent_factory3_bridge_20261014/README.md)。
各入口的可用版本與驗收狀態以[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)為準。

`source-pins.json` 固定五個公開來源，總共118,615 bytes；Python原始碼只雜湊，
不import、不執行。它驗證選定來源bytes，不驗證完整checkout、Git HEAD、
私人材料、原始review或實際遠端版本。

## 1. 產生不會啟動工作的計畫

在 repository root 執行。輸出父目錄須先存在，檔名須尚未存在。

```sh
mkdir -p .irisx/offline-continuation
python3 -B tools/arc2_sft_rl_continuation_20261014/cli.py prepare \
  --repository-root . \
  --output .irisx/offline-continuation/plan.json
```

輸出包含 SFT256、32 parents×8 samples、最多四個互斥64-slot批次、完整 B wall
配對 C、固定 dev 選擇、no-TTT、PUBLIC120／167，以及接收端必須保留的原始
collector／owner／checkpoint artifact名稱。清單的 `not_inspected` 不可改稱已具備。
原始材料缺失時保留blocker，不能由此計畫製造admission或成功收據。

## 2. 解讀已經存在的本地 collector 報告

取得原 collector 產生的 `TERMINAL-VALIDATION.json`，保留原始bytes，從獨立保存的
原始收據核對 SHA-256。自行計算hash只能核對檔案身分，不能建立外部收集真實性。
下例的 `LOCAL_COLLECTOR` 與大寫 SHA 都是須替換的佔位文字。

```sh
python3 -B tools/arc2_sft_rl_continuation_20261014/cli.py analyze \
  --report LOCAL_COLLECTOR/TERMINAL-VALIDATION.json \
  --report-sha256 SHA256_OF_ORIGINAL_VALIDATION_FILE \
  --output .irisx/offline-continuation/analysis.json
```

若原始 `TERMINAL-CHECKPOINT.json` 與 `RETRIEVAL-RECEIPT.json` 也有保存，可明確加上：

```text
--checkpoint LOCAL_COLLECTOR/TERMINAL-CHECKPOINT.json
--checkpoint-sha256 SHA256_OF_ORIGINAL_CHECKPOINT_FILE
--retrieval LOCAL_COLLECTOR/RETRIEVAL-RECEIPT.json
--retrieval-sha256 SHA256_OF_ORIGINAL_RETRIEVAL_FILE
```

這只核對報告之間的bytes／hash／狀態鏈，不會沿著JSON內的路徑找檔，也不會連線
下載。retrieval必須與checkpoint一起提供；每個檔名必須有其明確hash。
支援原batched consumer的 `irisx/owned-rl-batched-offline-validation-v1`；
舊SFT64／full-sweep schema不能靜默套用。格式不明的collector診斷可保留拒絕狀態，
不因此獲得可用分數。

## 3. 正確閱讀結果

- `OFFLINE_OUTPUT_WRITTEN`／exit0只表示寫出新檔，不表示輸入真實、完整或有效。
  檢查 `analysis_structurally_consistent`、`issues`、`declared_axes` 和 nullable 指標。
- `INPUT_REJECTED`／exit2是參數、檔案、hash、JSON或安全操作拒絕。
  錯誤不輸出私人路徑、原文錯誤或JSON內容。
- 合作式SIGINT／SIGTERM回報 `INTERRUPTED`／exit130；父程序仍須有timeout並等待
  真正結束。工具不派生訓練或網路子程序。
- 缺少scoring保留 `null`。只有原scorer已評分後的缺失／非法prediction才算錯；
  不把中斷或漏收變成0分。PUBLIC固定167queries；120tasks是預期值，compact report
  沒有task inventory，`task_count_verified`仍為false。
- 正確案例ID可算條件式gain／loss，但不能證明全部case相同；不輸出case IDs或答案。
  Dev count／tie一致不證明selection seal或先後順序，相關驗證旗標仍為false。
- B/C整段同步model-phase wall包含setup、抽樣、reward、replay、失敗／rollback、
  hash／Python、save／reload／verification；不能改成只配optimizer時間。
- 全零完整稽核、未完成、之前已commit而後續失敗要分開；整個B從未commit才檢查B=A。
  不得抹除先前完整更新或退回其實體成本。

所有聚合都以不可信本地JSON為條件。此companion永遠不建立authenticated collection、
method efficacy、promotion或下一輪dispatch authority。

## 4. 檔案安全與中斷後續接

輸入為明確指定的單一常規檔，最多16MiB；拒絕symlink、hardlink、FIFO、重複JSON key、
非有限數及不符hash。目錄與檔案使用no-follow descriptors，避免祖先替換把讀寫導向
另一棵樹；安全界限不是先呼叫一次 `is_symlink()`。

輸出使用受限staging與exclusive publication。既有或競爭產生的目的檔不覆寫；
偵測namespace／identity改變即拒絕，不回報另一檔案hash。暫存清理由持有的directory
descriptors進行，不沿交換後路徑操作。

exclusive publication成功後若後續檢查、fsync或程序終止失敗，完整目的檔可能已存在。
這時是**結果不確定，先檢查檔案**，不能直接重跑或刪除。工具不以stat-then-unlink移除
已發布檔，避免刪掉競爭者替換的檔案。接收端應在可信目錄核對完整JSON與SHA，保留
原檔，再選新輸出名稱。SIGKILL、斷電、惡意同UID程序或返回後namespace變更，不在
Python cleanup可保證範圍。敵對替換的foreign staging entries會保留，不能任意刪除。

若staging mkdir成功，但首次stat/open失敗而無法確認inode，空的0700目錄也可能保留；
工具不刪除未能綁定所有權的名稱。這與已修復的祖先交換導向錯誤位置是不同情況。

本工具不掃描／刪除任意舊暫存，也不替代OS使用者隔離或權限控制。

## 5. 測試與證據範圍

參見 [最終獨立審查](offline-continuation-review.md) 的精確結果與來源指紋。
normal與`-O`都要測；涵蓋source pin、非有限數、完整分母、固定配對、不可信宣告、
symlink／祖先交換、拒絕覆寫、失敗／中斷cleanup及CPU CLI。

真正原consumer的拒絕分支可用空的合成目錄做interoperability檢查；完整成功路徑的
歷史fixtures並未隨這次公開checkout具備。完整shape的合成報告只證明schema與聚合，
不是原run結果、full14B數值驗證、scorer重播或Kaggle狀態。

測試數字、CI 與缺失證據統一見[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)。
原始暫停 checkpoint `0451441` 的 race 與研究文件 `d13500c` 皆按其固定版本解讀；
不得將後續修復結果回寫為舊版本已通過。
