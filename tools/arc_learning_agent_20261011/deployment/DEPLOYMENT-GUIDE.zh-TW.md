# Learning + full-agent 發布與單次執行

此部署接續 2026-10-11 使用者核准的 private Git／Kaggle 發布與一個既有 GCP/BYOD GPU session。原 136 項 CPU 測試、37 個新增套件檔案及 97 個 runtime/scorer 檔案保持原始來源身分。完整 8B/G4 訓練、速度、記憶體和 ARC 正確率，仍須由實際 run 建立證據；不保證 public 50 分。

## 發布順序

1. 以 publication-manifest.json 的封閉 inventory 建立兩個新 private Dataset v1。code 保留既有權利與 other 標記；training 保留官方 Apache-2.0 原文及 800/200 split。
2. 完整下載核對版本、所有 bytes/SHA 和实际展開布局；只有已核對的八個 Dataset pins 才能掛載。
3. 新 notebook `danielwuu/iris-x-learning-agent-20261011` 的 inactive v1 為 QUICK_SAVE，MANUAL_START=False、ENABLE_MODEL=False、GPU/TPU/Internet=False。
4. 經審查的 run001 template 僅改 MANUAL_START、ENABLE_MODEL、OUTPUT_ROOT。唯一提交者在 durable intent 前填入一次 PREDISPATCH_EPOCH，記錄最終 source SHA、原始 deadline；不能重設時間或重送不確定的寫入。
5. 保存 active v2，SAVE_AND_RUN_ALL，既有 NvidiaRtxPro6000、原 Docker image、ARC-AGI-3 association。ARC3 僅掛載 metadata，solver 不讀取其 task data。

## 十二小時界線

- 原始提交前 epoch + 43,200 秒為不可延長的程式 deadline；排隊消耗也會扣除此預算。
- source admission、offline 安裝、model loading、訓練、TTT、推論、評分、封存，都在一個獨立 owned child 裡執行。notebook 父程序只做監督，於 deadline 前 30 秒開始停止 owned process tree。
- provider execution timeout 另設 42,300 秒，作為備援。外層 closure 獨立證明實際 child 結束時間和 descendants 回收；不能把較早寫出的 summary.remaining_seconds 當作封存完成證據。
- 這些控制界定程式實際執行時間。它們不提供平台 queue SLA、VM 釋放、網路可用性或計費停止保證。官方 API 未提供本次 session ID 映射時，不猜測 ID 或使用未支持的取消路徑。
- 若逾時、未知 work、所有者停止失敗或封存缺件，結果是明確不完整，不另啟新 session 假裝成功。

## 成功定義

Provider COMPLETE 還不夠。需要 exact active version/source、production 8B research 路徑、實際 global SFT optimizer update／adapter 改變／有限數值、完整 120 task attempts、generation work 無 unknown、model/子程序已停止、predictions seal、隔離 scorer SCORED、所有 ZIP inventory SHA 以及獨立 adapter 檔案核對，並有在原 deadline 內完成的 outer closure。PARTIAL_SCORED、PREFLIGHT_ONLY 和 renderer COMPLETE 都不是此次完整運行成功。

監控只讀 operational status、來源與封存證據。成功後停止監控；分數正確率留待另行分析。標準 LoRA、demo-only TTT 和 agent scaffolding 不等於全權重重訓或官方四張 L4 競賽提交。

## 證據與歷史檔案

release/historical-preparation/SOURCE-FREEZE.json 與 historical-preparation notebook 是前次 CPU 交付快照。它們的 development-only 註記是當時狀態。此次明確授權、wrapper/configuration 差異、實際 Dataset/notebook receipts 與 Git commit 分開記錄；不得回寫歷史證據。新部署 notebook wrapper 和 publication manifest 自有完整 SHA 綁定。
