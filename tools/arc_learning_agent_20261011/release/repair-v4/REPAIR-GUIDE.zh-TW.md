# Learning-agent v4 封存修復

## 結論

原 v4 已完成學習／推論工作程序，之後在讀取 34,228,110 bytes 的彙總 result.json 時超過既有 16 MiB 限制，因此 Kaggle 保留 ERROR。此次修復不更動原答案，不重新訓練或推論。

## 程式修正

- 將彙總內重複的逐題 evidence 移出；完整原始 owner 與逐題診斷仍保留，以 SHA-256、大小及固定相對路徑綁定。
- 所有預測格子、候選順序、三個政策、120 題／167 個測試分母、使用量事件、計量及階段資料不變。
- compact result 維持 16 MiB 上限；完整 owner evidence 另設 64 MiB 上限。缺檔、竄改、異常狀態或大小超限仍拒絕。
- worker 關閉前寫入並驗證 compact result，既有 live owner 關閉證明、prediction seal、原 scorer 與 CPU 資源限制均不放寬。

## 原 v4 的 CPU 恢復

歷史恢復是獨立協議：先核對 exact-v4 下載記錄、原 source、request、雙層程序關閉證明、原始 result hash、18,871 筆 ledger 與固定時限，再封存原答案。逐題 detail 僅以固定原 serializer 從不可變彙總重建，清楚標示為衍生資料。

先做不讀答案的 512 MiB proof-only 驗證；審核通過後，由新的隔離 CPU evaluator 執行原專案 scorer。此結果標示為「原 v4 生成答案的 CPU 離線評分恢復」。原 Kaggle v4 ERROR、不完整的原封存路徑及原 epoch/deadline 均不改寫。

CPU 恢復不取得模型權重或 adapter、不開啟新的 GPU 工作、不產生新候選、不修改排序。輸出是公開開發資料上的研究結果，不代表競賽四 L4 推論或官方分數。

## 發布

本次僅更新同一私人 code Dataset 的 v3 與同一 notebook 的 inactive v5；其餘七個 Dataset pins、Docker image 與 ARC-AGI-3 metadata association 保持原值。預設 MANUAL_START=False、ENABLE_MODEL=False、PREDISPATCH_EPOCH=None。沒有 RUN 分支；新的 GPU 執行需要另行授權。

Git 只收程式、測試及精簡 hash／狀態證明；原始 result、預測格子、資料集、ledger、詳細程序紀錄與模型權重不納入 Git。完整 CPU 恢復資料另存新檔，與原始 provider 證據分開。

## 驗證解讀

大型合成資料的真正 offline launcher、程序關閉、封存、隔離 evaluator 與 archive 路徑須通過。實際 v4 的新舊政策 pools 必須逐 byte 相等。focused suite 與整體 repository baseline 分開報告；既有歷史 CI 失敗不可改稱全綠。

本次不啟動新的 8B/G4 run；已通過的 CPU 測試不能代替修正版的未來 GPU end-to-end 實測。
