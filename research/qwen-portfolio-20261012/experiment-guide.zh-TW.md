# 下一輪：先把 checkpoint 的互補能力變成可驗證的選答方法

## 為什麼這樣改
v18 的 program LoRA update16 在六個已訓練轉換族的新網格上達5/6，base為2/6；update8和16各有擅長與退步的題目。原先只依一題已曝光development的grid NLL選checkpoint，最後仍選回base。這次不事後指定16，而是預先固定base、8、16全部保留，讓每題demonstrations決定哪些program可用。

原13題只作已看過的回歸資料。先前回顧性demo-only的6/6不列為新成果。

## 一次手跑內的比較
- 13題舊回歸
- 12題新網格、相同訓練轉換族
- 6題未進訓練的新轉換族
- 8題canary，父題與轉換族不進訓練，也不混進holdout指標
- 24題由固定雜湊抽樣的官方ARC training-source留出父題；將最後一個demonstration當query，原test欄位不保留

兩個獨立分支仍各16個optimizer updates，分別訓練grid與program。每個checkpoint先落盤，再由磁碟重載後生成。所有63題的候選、選答和棄答先封存，之後才開啟holdout答案計分。

Program portfolio 固定順序base→8→16，只允許通過全部demonstrations且query執行有效的program。最多交兩個不同網格，沒有合格候選就明確棄答。Global canary checkpoint排名另列為對照，不會刪掉portfolio候選。Grid selector看grid指標；program selector看program指標，不再用grid NLL替program挑checkpoint。

## 必須先過的工程條件
1. 原生Qwen tokenizer、完整詞彙head、BF16 base、FP32 rank8/alpha16 LoRA與來源雜湊一致。
2. 每個checkpoint保存真正adapter及完整optimizer、scheduler、RNG、資料游標、counter等邏輯狀態；物理工作帳本不倒退。
3. 乾淨重置後磁碟重載，token與NLL一致。完整實驗後再銷毀舊backend，重建一次backend，從program16磁碟狀態作固定canary推論核對。
4. 所有holdout選答在讀取答案前封存。錯誤、截斷、context超限和未完成均保留在原分母。
5. 模型與子程序完整關閉後封存；持久化權重和診斷ZIP分開，避免重演檔案大小限制故障。

## 怎樣判讀成效
分別看新同族、新族與24題真ARC三個stratum的pass@1/pass@2，以及相對同題base的新增答對/新增答錯。Canary用於開發選擇，不能當獨立成績。若portfolio在新holdout沒有淨增益，先查demo-fitting誤接受、候選互補、截斷及訓練覆蓋，再決定下一次訓練資料；不能透過換分母或挑已知答對的checkpoint宣稱改善。

這不是PUBLIC120評分，更不代表已達90%。第一版仍只訓練六個authored families，真ARC是轉移評估。另有固定32題真ARC訓練資料與demo-verified witness API，尚未啟用，也沒有自動產生假gold program。

## 預算與已知限制
以v18量測及新面板實際native prompt長度回算，保守總預估約8小時43分，包含1小時IO/重新載入reserve。這是歷史量測估算，不是新GPU速度保證。程式從首次主動啟動開始最多12小時，包括安裝、hash、載入、訓練、評分及封存。GPU在使用者開始執行前的配置/閒置時間與實際帳單不由此時鐘證明。

24題真ARC在2048context、256輸出預留下，grid可生成21題、program可生成20題；未符合者仍在24分母。沒有依答案長度或模型結果換題。更大context需另作記憶體與效能驗證。

本輪BF16控制不混入FP8。4×L4推論、FP8速度/準確率、14B新面板實際準確率，均須後續實測，不能由CPU測試推定。

## 執行與下載
完整來源包與code Dataset候選是本地建置成果。Notebook預設MANUAL_START=False、ENABLE_MODEL=False，候選code版本10尚未遠端發布時，不能直接拿現有版本9當作相同程式。

確認精確來源掛載後，兩個開關改True；PREDISPATCH_EPOCH保持None，首次啟動記錄新的時鐘。使用新的輸出/來源目錄，不覆寫舊v18。不要手填舊epoch。

結束保留evidence.zip、terminal-receipt.json、checkpoints.zip、同名前綴的-launcher完整目錄與實際notebook。checkpoints.zip可能約1.6GiB，包含adapter與完整邏輯訓練狀態，不含14B base權重。即使PARTIAL或FAILED，也保留已寫出的檔案供定位與恢復。
