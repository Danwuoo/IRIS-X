# IRIS-X

IRIS-X 探索如何把領域材料、實際工作負載、需求與資源限制，轉成可量測、可選擇、可追溯的 AI 系統配置。核心方法是 **Domain Specification → Build–Measure–Select → Engineering Trial → Domain Package**；多個 Engineering Trials 分別保存基線、介入、量測與選擇，不把不同改善混為同一種效果。

Repository 包含 provider-neutral contracts、deterministic offline reference flow、package verification，以及 ARC-AGI-2 實驗與來源保全程式。產品方向見 [PRODUCT_THESIS.md](PRODUCT_THESIS.md)；產品目標不代表已完成可部署產品或已驗證模型優勢。

## 從工作線開始

先讀 [同步開發與工作線入口](docs/workstreams/README.md)。[registry.json](docs/workstreams/registry.json) 只索引狀態頁，不是執行設定或授權。

| 工作 | 入口 | 本階段邊界 |
| --- | --- | --- |
| 共用工程基礎 | [Core STATUS](docs/workstreams/core/STATUS.md) | contracts、reference flow、package、CLI 與測試基礎。 |
| ARC-AGI-2 | [ARC STATUS](docs/workstreams/arc-agi-2/STATUS.md) | 引用 run008 固定交接；保留現場，不以本次整理恢復執行。 |
| 第二線 | [line-b STATUS](docs/workstreams/line-b/STATUS.md) | 尚未指定領域；不預設為 ARC-AGI-3，也不宣稱已有實作。 |

這次 foundation 從 main 的 `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89` 分出；run008 的 `cc14bd1a79aac1fe6135017c9e09d4834300675d` 是另一條線的來源錨點，**不是已合入此工作樹的程式**。跨分支證據使用 commit-pinned 連結。各線的目前摘要只更新自己的 STATUS；歷史 trial README 與 review 保留原身分。

## P1 合成資料範例

需要 Python 3.11 以上。這是 provider-neutral 的合成工程流程，不下載模型、不上傳 Kaggle，也不是實際 ARC 能力測試。使用新的本地輸出目錄：

```sh
python -m pip install --no-build-isolation -e .
irisx fixture prepare --output .irisx/quickstart/fixture
irisx spec validate .irisx/quickstart/fixture/specification.json
irisx trial validate .irisx/quickstart/fixture/trial.json
irisx trial run --trial .irisx/quickstart/fixture/trial.json --output .irisx/quickstart/run
irisx package build --run .irisx/quickstart/run --output .irisx/quickstart/package
irisx package verify .irisx/quickstart/package
```

輸出留在 ignored `.irisx/`；不要覆蓋既有結果。Package verification 只支持其契約範圍，不能把合成結果或 `deployable: false` 改稱已部署模型。

導覽的獨立檢查與完整交接檢查分開：

```sh
python -B tests/test_workstream_navigation.py
python -O -B tests/test_workstream_navigation.py
python tools/repository_check.py --all
```

測試依賴與既有失敗見 [tests/README.md](tests/README.md)。導覽通過不等於產品、完整 CI、GPU 或 PUBLIC120 通過。

## 固定快照與歷史結果

code18／run005 的未成功執行快照仍由 `irisx-code18-run005-snapshot-20261013` 保存；runtime commit 是 `dbf21033b41aff9327cf4f91159df0133529f176`。當時最後核對 notebook v35 為 `CANCEL_ACKNOWLEDGED`，沒有新 PUBLIC120 結果。完整邊界見 [快照紀錄](docs/plan/2026-10-13-code18-run005-repository-snapshot.md)、[RUN005 binding](tools/arc_qwen_rlvr004_20261013/driver_path_repair/RUN005-BINDING.json) 與 [REBUILD](tools/arc_qwen_rlvr004_20261013/driver_path_repair/REBUILD.md)。這次不移動 tag、不改 runtime bytes、不重設時鐘。

Decision 0010 定義輕量開發；Decision 0012 保存 [Trial 001 status page](trials/first-real-domain/README.md) 的 `inconclusive-no-promotion`。Decision 0014 與 Decision 0015 保存 [Trial 002](trials/arc-agi-2-baseline/README.md) 已消耗的有界 smoke：四個 valid grids、local exact-match 0/4；不是完整 public-evaluation 表現，也不是後續 run 的結果。詳見 [決策索引](docs/decisions/README.md)。

固定前的 [CI run](https://github.com/Danwuoo/IRIS-X/actions/runs/38353809559) 曾記錄 1,578 tests、5 failures、96 errors、110 skips；不能把它或 run008 的紀錄當成本 PR 的測試結果。新 PR 的實際驗證以該 PR 的 checks 與報告為準。

## 資料與文件

權重、原始預測、完整 provider receipts、詳細 process logs、credentials 與 evaluator-only 答案不進 Git。可重建封包不必為導覽工作重新下載；原始輸入、歷史證據與重建依賴仍須保留。重整不代表允許刪除它們。

[檔案結構](docs/repository-layout.md) 說明現有路徑與遷移邊界；[開發方式](docs/development/operating-model.md)、[產品文件](docs/product/README.md)、[完整文件索引](docs/README.md) 與 [AGENTS.md](AGENTS.md) 提供其餘入口。[archive/](archive/README.md) 是早期 Git 歷史目錄，不是目前工作佇列。
