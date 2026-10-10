# 單一 Notebook 操作指南

## 這份 Notebook 會做什麼

同一份 Notebook 依序完成：獨立正負控制、固定示範題的表示能力檢查、候選排序診斷，以及通過可測性門檻後的選配模型實驗。各階段會保存 checkpoint、實際用量與失敗原因，最後封存 evidence ZIP。

模型階段共用一次載入的模型與初始候選，包含 true/redacted feedback、memory off/on、三種搜尋排序。上限為 80 次實際生成，加上 4,608 次新 CPU 搜尋驗證；共享生成只計一次，不會把多個 arm 當成獨立呼叫。

## 開始方式

1. Notebook 預設 `MANUAL_START=False`、`ENABLE_MODEL=False`、`PROFILE='SMOKE'`、`RESUME=False`。直接 Run All 保持未啟動，不安裝、不載入模型，也不寫入原始碼。
2. 先以 CPU 驗證：設 `MANUAL_START=True`，保留 `ENABLE_MODEL=False`。SMOKE 完成 128 個正負控制與 128×8 個候選檢查，共 1,152 次；此模式永遠不開模型門檻。
3. 完整表示能力檢查：換一個新的 `OUTPUT_ROOT`，設 `PROFILE='FULL'`。固定 5,965×8 個候選加 128 控制，共 47,848 次；CPU 階段最多 1,800 秒、同時最多四個隔離 worker。到達時間上限會保留 partial/inconclusive，不能把未檢查者當成失敗。
4. 只有完整 FULL、128 控制全部符合預期、ledger 完整，且至少兩個工程題有全部示範吻合的候選，才允許選配模型階段。即使已設 `ENABLE_MODEL=True`，門檻未過也不會安裝或載入模型。是否另行執行 G4 GPU 實驗仍由你決定。

## 模型與資料

後續 G4 模型實驗使用既有五個固定版本的私有 Dataset：runtime/8、Granite 4.2 8B offline/2、cu128 CP312 wheels/1、CPython312 offline/2、run003 adapter/1。完整名稱與 manifest hash 見 `validation/publication-manifest.json`。Adapter 僅核對相容性，本研究不載入它、不訓練。

預設 `MODEL_CONFIG={'input_root':'/kaggle/input','explicit_roots':{}}`。只有通過 FULL 門檻及手動允許模型後，才開始檢查 Dataset、離線準備 CP312 環境與載入模型；不需要手動填入權重或 interpreter 檔案路徑。資料來源根目錄必須與 source/cache/output/environment 分離。

## 中斷、重跑與下載

- 新實驗使用新 `OUTPUT_ROOT`；SMOKE 不能改名接續成 FULL。
- 接續同一實驗須保留完全相同的 source、資料、sampling、budget 與 config，明確設 `RESUME=True`。不同版本不能接續彼此的 ledger。
- 呼叫前即保存並 fsync reservation。已送出但沒有回覆的呼叫列為 unknown、全額計入用量，不會自動重送。
- 模型回覆已存在但驗證缺失，可另計一次 CPU 驗證；不將它偽裝成免費驗證。
- 下載輸出根目錄下 `archives/evidence-*.zip`。封存必須具備所屬 verifier 與模型程序的停止證明。
- 程式結束或 ZIP 完成不代表付費 VM 停止計費；VM 仍需另行關閉。

## 解讀限制

八個題目是已暴露的工程示範題，全部保留在分母。Demo-fit 只證明固定表示與資源上限內存在吻合示範的程式。它不是 query/held-out 分數，不改變原 N14 晉級門檻，也不能代表 ARC-AGI-2 泛化。

Linux CPU、隔離控制、ledger 與 mock 流程的驗證狀態見 `VALIDATION.md`。實際權重、tokenizer、四個其餘掛載、離線安裝、G4 GPU 與四張 L4 提交流程仍未經實機驗證。
