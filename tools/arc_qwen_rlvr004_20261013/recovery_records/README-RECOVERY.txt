IRIS-X run006 原始碼救援包（2026-10-13）

已救回32個最終來源檔或紀錄，每個都與遺失前保存的 SHA-256 完全相符。包括主要修復程式、組裝程式、相關測試，以及部分原審核紀錄。

目錄說明：
- exact-originals：與原先最終雜湊完全相符的檔案。
- frozen-reference：已核對的舊版參考檔。
- earlier-versions：已核對的較早版本，不可冒充最終版。
- incomplete-literal-fragments：仍不完整的原始片段。
- recorded-literal-patches：保留的原始修改片段；其套用結果已比對最終檔案雜湊。
- literal-records-without-original-digest：完整保留內容，但缺少遺失前雜湊可獨立核對。

完整原始 release ZIP、patch 與交接檔仍未取回。最終 operator transport 與一份 launcher 測試也有缺口；詳見 RECOVERY-MANIFEST.json。

這個救援包沒有補寫缺失程式，也沒有重跑專案測試、Kaggle 或 GPU 工作。原審核紀錄僅保留作歷史證據；此目錄排列不是完整可直接執行的 repository。未包含憑證或 gold 資料。
