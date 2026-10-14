# IRIS-X

IRIS-X 探索如何把領域材料、實際工作負載、需求與資源限制，轉成可量測、可選擇、可追溯的 AI 系統配置。核心方法是以 **Domain Specification → Build–Measure–Select → Engineering Trial → Domain Package** 組織實驗，而不把模型、prompt、工具或搜尋的改善混為同一種效果。

Repository 包含 provider-neutral contracts、deterministic offline reference flow、package verification，以及 ARC 實驗、來源封裝與結果保全程式。產品方向見 [PRODUCT_THESIS.md](PRODUCT_THESIS.md)；產品目標不代表目前已完成可部署產品或已驗證模型優勢。

## ARC-AGI-2 研究線目前進度（2026-10-14 UTC）

目前研究線的狀態、任務、依賴、證據與下一步，統一見
[開發進度管理](research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md)。
方法、使用方式及固定審查紀錄見[研究文件入口](research/arc2-sft-rl-continuation-20261014/README.md)。
下面保留各版本的歷史快照，不代表本研究線的最新進度。

## 歷史固定版本與執行紀錄

2026-10-13 UTC 已從 run007 移轉 commit `2901a97` 開啟新的 native research
分支，先完成歷史研究整理，再修復 cuDNN loader 並保留既有受控實驗。
新的循環包含提交後監看、抓取結果與下一輪；詳見
[研究與實驗計畫](docs/plan/2026-10-13-native-research-continuation.md)。
目前 v39 仍是 ERROR，沒有新的 PUBLIC120 分數；原 code18 失敗快照保持不變。
下列固定版本紀錄是歷史保存，不表示新的分支已完成 GPU 驗證。

2026-10-13 的 **code18／run005 原始碼快照已固定，開發與外部執行停止**。完整來源、狀態與重建邊界見 [快照紀錄](docs/plan/2026-10-13-code18-run005-repository-snapshot.md)。

| 項目 | 固定紀錄 |
| --- | --- |
| Snapshot tag | `irisx-code18-run005-snapshot-20261013` |
| 已發布 runtime commit | `dbf21033b41aff9327cf4f91159df0133529f176` |
| Run identity | `irisx-qwen14b-rlvr-20261012-run005` |
| 最後核對的 saved notebook 狀態 | v35：`CANCEL_ACKNOWLEDGED`；未觀察到 `RUNNING`。 |
| 新 PUBLIC120 分數 | **沒有結果**；不是 0，也不能沿用舊版本分數。 |
| 已建立的範圍 | 原始碼重建、封裝身分與部分 CPU／部署檢查的歷史紀錄。 |
| 尚未建立的範圍 | 完整 GPU inference、sealed predictions、完整分母評分、model closure 與 operational success。 |

這是一個可重建來源的未成功執行快照，不是成功的模型 baseline。另有使用者回報的手動 Editor 錯誤，但缺乏可核對版本與 inner exception，不推定其根因。新文件提交不移動 snapshot tag、不改 runtime bytes，也不重設既有執行時鐘或啟動新的實驗。

## 從哪裡開始

| 路線 | 入口 | 內容 |
| --- | --- | --- |
| 產品與方法 | [PRODUCT_THESIS](PRODUCT_THESIS.md)、[產品文件](docs/product/README.md) | Domain Specification、trial、package 及產品邊界。 |
| 目前 ARC2 研究線 | [開發進度管理](research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md)、[文件入口](research/arc2-sft-rl-continuation-20261014/README.md) | 唯一進度與計畫入口，以及方法、使用與歷史證據導覽。 |
| 離線工程基礎 | [src/irisx/](src/irisx/)、[tests/](tests/README.md) | P1 contracts、reference flow、package verification 與對應測試。 |
| 歷史 code18 固定來源 | [快照紀錄](docs/plan/2026-10-13-code18-run005-repository-snapshot.md)、[RUN005 binding](tools/arc_qwen_rlvr004_20261013/driver_path_repair/RUN005-BINDING.json)、[REBUILD](tools/arc_qwen_rlvr004_20261013/driver_path_repair/REBUILD.md) | 精確來源、封裝指紋、重建命令和缺失的外部證據。 |
| 歷史實驗 | [trials/](trials/README.md)、[research/](research/README.md) | 各 trial／研究版本的問題、實作及結果；不得跨版本移植分數。 |
| 決策與開發 | [決策索引](docs/decisions/README.md)、[開發文件](docs/development/README.md) | 設計取捨、資料及執行邊界。較早的執行授權依固定紀錄視為歷史。 |
| 早期版本 | [archive/](archive/README.md) | Pre-product repository 的唯讀目錄，不是現行產品狀態。 |

初次閱讀可先看產品目標；ARC2 續接開發從目前研究進度進入，P1 使用者可看離線流程，
重建歷史 code18 才使用其固定來源。不需要順讀全部歷史 decision／handoff 文件。

## P1 合成資料範例

需要 Python 3.11 以上。這是 provider-neutral 的合成資料工程流程，不下載模型、不上傳 Kaggle，也不是實際 ARC 能力測試。安裝與執行會產生本地檔案：

```sh
python -m pip install --no-build-isolation -e .
irisx fixture prepare --output .irisx/quickstart/fixture
irisx spec validate .irisx/quickstart/fixture/specification.json
irisx trial validate .irisx/quickstart/fixture/trial.json
irisx trial run --trial .irisx/quickstart/fixture/trial.json --output .irisx/quickstart/run
irisx package build --run .irisx/quickstart/run --output .irisx/quickstart/package
irisx package verify .irisx/quickstart/package
```

生成檔留在 ignored `.irisx/`。Package 建立／驗證只支持其契約範圍，不能因此把合成結果或 `deployable: false` 的產物改稱已部署模型。這些是既有使用入口，本次文件更新沒有重新執行該流程。

Repository 檢查入口：

```sh
python tools/repository_check.py --all
```

精確 code18 來源重建請依 [REBUILD.md](tools/arc_qwen_rlvr004_20261013/driver_path_repair/REBUILD.md) 與快照紀錄操作，使用新的 ignored output directory。完整 operational assembly 另需 Git 外的 authenticated predecessor evidence 與既有獨立驗證；來源重建不等於 GPU 執行或發布授權。

## 結果與驗證範圍

早期 [Trial 001](trials/first-real-domain/README.md) 結束為 `inconclusive-no-promotion`，沒有完整 measurement、selection 或 Domain Package；[Trial 002](trials/arc-agi-2-baseline/README.md) 的有界 smoke 保留四個 valid grids、local exact-match 0/4，不能外推成 public-evaluation 表現，也不是 code18 的結果。

Code18 快照紀錄保存 focused driver、assembler、operator 與 CPU simulation 檢查，但沒有完成真實鎖定環境的端到端 GPU launcher 驗證。固定前的 [完整 CI run](https://github.com/Danwuoo/IRIS-X/actions/runs/38353809559) 記錄 1,578 tests、5 failures、96 errors、110 skips，其他三個 jobs cancelled。Repository checks 的通過與部分 CPU tests 的通過，不能替代 full CI 或實際模型成功；本次文件修改沒有修復或豁免這些失敗。

## 資料與版本保存

模型權重、原始預測、完整 provider receipts、詳細 process logs 與 credentials 不在 Git。公開答案保持 evaluator-only；既有失敗、停止狀態、分母、來源和封裝指紋均保留。不要以新的資料、重新打包產物或舊實驗分數補成固定版本的成功結果。

完整文件索引見 [docs/README.md](docs/README.md)，開發約束見 [AGENTS.md](AGENTS.md)。README 是專案與版本導覽，不改寫產品契約、科學結果或歷史紀錄。
