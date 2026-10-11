# Learning-agent v2 啟動修復

## 已確認的原因

Kaggle v2 在學習 worker 執行前結束。已驗證的 offline-run.py dispatcher 收到 `-I` 作為第一個 script 參數，因而把它當成檔名並拋出 FileNotFoundError。不是已證實的模型、資料或訓練錯誤。

## 最小修復

- 已驗證的離線 Python command prefix 原樣保留；worker、request 與 SHA 直接接在 dispatcher 後面。
- tiny CPU 直接 Python 路徑仍保留 `-I`、`-B` 隔離，且旗標在 dispatcher 前。
- replacement bootstrap 的 1,800 秒 allowance 以本次實際 monotonic 工作時間計算，同時受原 global deadline 與 3,600 秒收尾保留約束。耗盡即拒絕，不填入假的正數 timeout。
- 只有 session.py 的 runtime 行為改動。其餘 96 個 runtime/scorer 檔案、模型、訓練資料、實驗方法與外層 watchdog 均保持原 bytes。

## 發布與重啟

同一私人 code Dataset 由 v1 更新到 v2，保留舊版；同一 notebook 138123872 先保存 inactive v3，再提交經核准的 replacement v4。其他七個 Dataset pins 不變。每一版本使用全新的輸出與 source 目錄，不覆寫 v2 失敗證據。

原始 epoch 為 1791697978，固定截止為 1791741178（2026-10-11 17:52:58 UTC，台灣時間 10 月 12 日 01:52:58）。replacement 不重設時計。Provider timeout 取原截止剩餘秒數扣 900 秒，且不超過 42,300 秒。平台排隊與計費結束不在本程式可保證範圍內。

依使用者最新指示，只在核對正確版本、GPU、既有 ARC-AGI-3 掛載與 RUNNING 證據後停止監看，不等待終態或分析研究結果。

## 驗證範圍

新增回歸涵蓋原錯誤重現、實際 trusted launcher、直接 Python 及額外旗標、網路 guard、過期與縮減的全域時間、stage cap，以及真實兩題 tiny-neural 訓練／adaptation／封存／獨立評分。wrapped end-to-end 特別沿用 2,400 秒前的起點，核對原始 deadline 沒有被延長。

完整 8B/G4 的訓練、VRAM 與正確率仍須實際 run 驗證；CPU fixture 的成功不等同 public 分數或 GPU 成功。

## 重跑 CPU 回歸

在 repository 根目錄，使用已備妥且包含 Torch/Transformers/PEFT 的 Python 3.12，設定 CUDA_VISIBLE_DEVICES 為空、HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1、ARC_LEARNING_NEURAL_TESTS=1、ARC_NATIVE_TOKENIZER_PATH 指向已驗證 Granite tokenizer 的小型資產目錄、PYTHONPATH=src:.，並令 TMPDIR 位於 repository 以外。

另外，既有 native-head 訓練測試會固定讀取 repository 旁的 `tokenizer-assets/` 目錄；請將同一份已驗證的小型 tokenizer 資產放在該 sibling 目錄。只設環境變數不足以覆蓋這一項測試，缺少時會明確 skip。

執行 `python -m unittest discover -s tools/arc_learning_agent_20261011/tests -t . -v`。測試的 synthetic fixtures 不可標示為實際 PUBLIC120 推論成績。
