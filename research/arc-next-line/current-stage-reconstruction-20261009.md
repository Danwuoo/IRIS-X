# 研究階段來源重建說明

記錄日期：2026-10-09。本文是新的整合紀錄，不是遺失 commit 或歷史驗收檔案的原貌還原。

## 可驗證的基礎

- 本次整合前核實的私人 repository main 為 `077bb4680706b95f196621dab4360ffe03504354`，tree 為 `1ae392744a4236b3fbec61b73461e985f9a51487`。真正提交前仍須重新確認遠端未前進。
- 原始 `RESEARCH-SUMMARY.zh-TW.md`、`architecture-memo.zh-TW.md`、`model-hardware-memo.md`、`model-source-lock.json` 與 `validation/public-training-readiness.json` 都仍在 main。保留其歷史證據，不以手工重建替換已存在的原始檔案。
- 2026-10-08 曾準備但未驗證推送的本機末端為 `7c1d94f4a90080fc5b460e799b4be2f95c93a176`、tree `b9fec9002999a1ebed0f1f44a7b3b3ce45d312c0`。原工作目錄和其增量 bundle／ZIP 現在不可取得。已知識別碼及先前對話報告不等於恢復了 Git objects、原始驗收檔或九個未發布 commits。
- 當時的完整 source、tests、receipts 與後續規劃並未全部包含在 runtime Dataset 中。本次只能從實際可讀、逐檔核對的 runtime/6 deployment snapshot 匯入可驗證的 source members，再加上獨立檢視過的新修補。必須記錄每個匯入檔案的來源和雜湊；不宣稱整個 `7c1d94f` tree 已重建。

## 研究結論仍成立的範圍

保留的 uncapped NVARC 小型實驗完成六個 tests、41 個不同候選；top-1、top-2 與候選池 oracle 都是 1/6。另五個候選池沒有正解，單純重新排序不能補回不存在的答案。這支持測試更好的提案、表示法與訓練，不證明新 agent 架構已有效，也不是官方分數。

A direct-grid、B 程式提案加 demonstrations 驗證、C 執行失敗回饋修復，仍須同模型與可比預算的實測。AVO、Duck、Prime 等工作提供方法參考；ARC-AGI-3 結果不是本案 ARC-AGI-2 成績。Granite 優先、Qwen3.5-9B 次之、Seed-Coder-8B-Reasoning 再後，是研究／取得順序，不能代替實測品質排名。

## 最新執行與修補界線

先前私人 notebook `137711693/version1` 由使用者手動執行後回報失敗。新的診斷識別出 Transformers loading-info 的 set 值無法直接寫入 JSON；窄幅修補包括已知欄位的可序列化 receipt，以及保留原始子程序錯誤／traceback。不要把 CPU 修補驗收稱為成功完成 GPU 訓練。

本次新的 runtime 版本、notebook QuickSave 版本、Git commit、逐檔來源與實際 CI，必須由本次收據填入；不得先填預期版本或改寫舊收據。CPU 驗證、完整模型載入、128 個 optimizer updates、品質提升與四 L4 正式提交準備，是不同的驗收層次。

先前對話曾報告 1,677 個 aggregate tests、35 errors、3 failures、78 skips，兩個 timing-sensitive tests 的單獨重跑通過。由於原始完整 log 目前不可取得，此數字只能保留為前次回報，不能當成本次新 checkout 已通過的測試。新整合須重新跑適用測試並記錄實際失敗、skips 與未執行項目。

## 本次保存範圍

使用者已確認上傳並 push main。單一寫入者從最新 main 建立整合，保存無關改動與既有 ancestry，採正常 fast-forward／expected-head 的非強制更新。Git 僅保存必要 source、測試、經清理的證據與重建文件；不加入 credentials、weights、wheelhouse、Python binaries、原始答案或大型執行輸出。不以任何舊的待核准請求代替本次明確回執。
