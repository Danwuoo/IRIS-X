# 故障與回歸測試對照

這份對照說明哪些風險已在開發環境實際測過。測試通過不等於新面板準確率提高。

| 風險 | 本輪可重現檢查 | 仍未證明的範圍 |
| --- | --- | --- |
| PEFT 把 target_modules 列表正規化成集合或縮寫後，嚴格比較誤拒絕 | 真正四層 Qwen/PEFT、28 個 LoRA targets、完整 151,936 詞彙 head，保存與重載測試 | 新一輪 14B GPU 執行尚未開始 |
| 診斷輸出超過一般 16 MiB 上限 | 實際 34,228,110-byte 診斷 JSON 封存與雜湊往返；一般檔案 16 MiB+1 仍拒絕 | 未宣稱所有可能的輸出大小都已實測 |
| Adapter/optimizer 檔案被當作一般小型證據，導致封存失敗 | 實際兩個 32 MiB byte shards、超過 64 MiB 的獨立 ZIP 往返；32 MiB+1 shard 拒絕；完整資產清單先核對才排除於 evidence.zip | 此大小測試使用合成 bytes；約 1.6 GiB 的完整 14B checkpoint ZIP 尚未實測 |
| 只保存模型參數，續訓時 optimizer、scheduler、RNG 或資料游標遺失 | 真正 tiny 模型從 update16 磁碟恢復後執行 update17，完整狀態與不中斷路徑一致 | GPU 速度、記憶體與浮點重現仍須新手跑量測 |
| 同一記憶體中的 restore 被誤稱為可獨立載入 | 完整 63 題 owned CPU 流程最後先銷毀舊模型，重新建立 backend，再由磁碟載入 program16；token、finish reason、NLL 核對一致 | 使用隨機 tiny 權重，不是 14B 準確率測試 |
| 程序失敗後未清理或把失敗當成功 | 真實模型載入後注入故障，保留診斷 ZIP、乾淨關閉 owned tree，狀態仍為 FAILED | 尚未做所有硬體故障的注入 |
| 浮點相減誤判 deadline 超限 | 使用 endpoint 比較與精確 deadline 公式，保留嚴格超時拒絕 | 不提供外部可信時間戳認證 |
| 把 VM 的 JSONL response 當成單一 JSON，或廣泛忽略解析錯誤 | 真正兩階段 VM stream 與正常、變更欄位、階段、形狀、路徑、request、輸出與 aggregate 的反例測試 | 離線驗證核對來源與收據，不是重新執行每個模型或程式 |
| 用 holdout 答案挑 checkpoint，或遺漏失敗題縮小分母 | 315 個候選/題目位置完整封存，重算固定 demo-only portfolio 與八題 canary 排名，之後才開啟 target escrow | 新 holdout 不代表未出現在模型預訓練資料 |
| 手跑 notebook 改動後仍套用舊 server admission | 核對完整可執行 cells，只接受明訂手動開關、來源/輸出位置和時鐘契約；缺 notebook 或 launcher 時明確標為未提供 | 不由上傳檔案推定 Kaggle provider 的執行狀態 |

原生離線安裝器與既有 157 個來源檔保持原樣；本輪重測新 notebook 的來源布局與無模型入口，但沒有重新安裝全部 52 個 wheels。完整來源包中的測試說明列出需要原始外部 fixture 的歷史檢查，沒有把缺資料的跳過當成通過。
