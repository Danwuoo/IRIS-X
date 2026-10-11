# Learning-agent v6 封存邊界修復

## 已確認的失敗

Kaggle 同一 notebook 的 v6 保持原始 ERROR 記錄。已下載的精確版本證據顯示：原 owner 正常退出，summary 的 operational 狀態為 COMPLETE、solver complete、SCORED，最後在 export.py 拋出 `output symlink forbidden`。

離線安裝器會在其安裝目錄建立合法的 wheelhouse 目錄連結。舊 exporter 雖然原本就打算排除整個安裝環境，卻先遞迴掃描及拒絕連結，之後才判斷排除。這讓兩個各自通過測試的契約互相衝突。實際 traceback 沒有印出第一個連結的名稱；固定安裝程式與同結構 CPU 重現提供該衝突的證據。

## 修復範圍

只調整封存檔案的邊界：安裝 payload 在進入目錄前排除；保留綁定於 bootstrap receipt 的少量固定證明檔。其餘證據中的連結、非一般檔案、路徑越界、變動或雜湊不符仍拒絕。模型、訓練、推論、候選排序、評分、資料、資源上限與程序關閉要求不變。

## 保全已有結果

這次原 run 已寫出 prediction seal 與 scorer 產品。CPU 恢復優先核對並封存這些既有 bytes，不重新產生答案或重新挑選候選，也不需要再次 GPU 執行。另產生的恢復 archive 必須清楚標示為下載後的封存恢復，不能冒充原 run 已成功輸出的 archive，不能將 provider ERROR 改成 COMPLETE。

原結果的 120 題／167 測試、三個 policy、source/request/owner/ledger/評分綁定都需驗證。任一缺失不能以猜測、空檔或偽造的 live process proof 補上。完整原始資料保留在獨立恢復檔，Git 僅收修補程式、測試與精簡來源／驗證紀錄。

## 為何前輪測試漏掉

前輪 168 項測試確實通過，包括 tiny 神經訓練、offline launcher、超過 16 MiB 的原結果投影、封存與隔離 evaluator。但 tiny 路徑不執行 production bootstrap，超大投影整合案例也沒有真實安裝環境的目錄結構。這次需把安裝器實際產生的連結結構接到完整 owner→prediction seal→原 evaluator→export 流程，並驗證排除與保留邊界，不能只依賴各模組分開通過。

測試中的合成網格／tiny CPU 訓練只驗證工程流程，不作為正式 8B 成績或成功聲稱。原 v6 的實際生成／評分產品與新增 CPU 封存驗證分別標示。

## 發布與執行

擬發布同一私人 code Dataset 的 v4 與同一 notebook 的 inactive v7，保留 v6、所有歷史 Dataset 版本及其他七個 pins。預設不執行模型；沒有新 RUN 分支。任何後續 GPU 執行需另有明確授權。
