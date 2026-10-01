# NVARC 資料下載與本機處理

Date: 2026-10-01
Status: download, local processing and independent verification complete.
Authority: [Decision 0049](../../docs/decisions/0049-acquire-and-audit-nvarc-datasets.md).

## 取得與保存

以本機 Kaggle CLI 的明確 `/1` selector 下載兩包資料；沒有使用會刪除原 ZIP
的 `--unzip`。原 ZIP、檔案 inventory、資料、labels 和本機 logs 均在 ignored
`.irisx/nvarc-data/`，Git 僅保存程式與本報告的來源、counts、限制及摘要 hashes。
CLI 回報兩包 license 為 `unknown`；本次沒有上傳、公開散布或宣稱再授權。

| Dataset | 固定版本 | ZIP bytes | 解包 bytes | Members |
| --- | --- | ---: | ---: | ---: |
| [Augmented Puzzles](https://www.kaggle.com/datasets/sorokin/nvarc-augmented-puzzles/versions/1) | 1 | 1,322,144,874 | 11,967,256,864 | 42 |
| [Synthetic Puzzles](https://www.kaggle.com/datasets/sorokin/nvarc-synthetic-puzzles/versions/1) | 1 | 338,160,847 | 5,792,311,411 | 103,223 |

原始 ZIP SHA-256：

- augmented：`5e6599d8ea34f05c42bb936a33d9d1b80ac1196d7f70c8d99d1bbd9a9cb3fdfd`
- synthetic：`84e33a1a042fe3fa699423f4b63f1b8091d90c9fd3db4f19efc2e4c8c9715f3b`

已逐一讀完所有 ZIP members，通過 CRC，保存每個 member 的 SHA-256 與長度。
解包前拒絕 traversal、Windows device/ambiguous paths、symlink、duplicate/case
collision 和 file/directory 衝突；原 augmented tree 再做閉合 inventory 比對。
Synthetic 保持 ZIP，直接串流讀取，避免產生十萬個零散檔案。

## Parent 與 exposure 查核

固定 NVARC source commit `846d0198efa752534594e321fc3289fc0a06c657`。
ARC-AGI-2 catalog 有 1,000 training 與 120 evaluation IDs。RE-ARC 的 400
generator IDs 經靜態 AST 解析，比對其原 ARC training ZIP；其中九個不在
ARC-AGI-2 training，仍有原公開 training 身份。沒有執行 generator/program。
Mini/Concept parents 依各來源 JSON 檔名登錄，使用來源 namespace。

Synthetic filenames 是 `parent1_parent2.json`，且外層 batch 等於 parent1。
每題保留兩個 parent（相同者去重），augmentation 的 `puzzle_name` 必須能
join 回同一來源的 synthetic member；未知或缺失 lineage 不得進入 filtered HF。
這是已發表檔名與 source naming 的 ancestry，未獨立重建 teacher mix 的語意。

| Synthetic subset | 原始題數 | 通過雙親排除 | Protected parent | Evaluation parent |
| --- | ---: | ---: | ---: | ---: |
| nvarc_training | 47,337 | 33,771 | 13,566 | 0 |
| nvarc_full | 55,886 | 0 | — | 55,886 |

通過查核的 33,771 題共 995,408 組結構有效 input/output pairs，每題 12–30
組；逐一檢查 1–30 的 rectangular grids、整數 colors 0–9 與 pair fields。
Evaluation/protected 題只登錄 ancestry 與隔離原因，沒有解析其 pair 內容。
這不是重新驗證原 teacher programs 或 semantic correctness 的聲明。

保護名單包含舊 pilot 16 parents、新 provisional dev 8 parents、原 locked
holdout 128 parents 和先前 smoke 4 parents；聯集及 visible color-renamed
duplicate family closure 共 153 IDs。原 split digest 精確匹配
`sha256:6176d88ce9a66dcc45584aa09c110898c0f782b1f97e42e1f268c3ef1f25bd2b`。
沒有執行 holdout 推論或評分，也未輸出 holdout answers。

## Augmented 篩選與訓練材料

每筆合格來源檢查完整 user/assistant alternation、grid text、compact chat
token 數與 assistant-only supervised token 數。保留來源順序及原始 row index。
本輪使用 8,192-token **本機 review cap**；超長紀錄原樣保存在原資料，列入
quarantine，沒有截斷。這不是已批准的 SFT context、步數或訓練預算。

| Source | 原始 records | Filtered HF records | Protected | 超長 | Evaluation |
| --- | ---: | ---: | ---: | ---: | ---: |
| arc2_training | 155,904 | 131,840 | 23,808 | 256 | 0 |
| mini | 37,632 | 37,632 | 0 | 0 | 0 |
| concept | 40,960 | 40,960 | 0 | 0 | 0 |
| rearc | 102,392 | 86,751 | 15,355 | 286 | 0 |
| nvarc_training | 1,132,633 | 804,372 | 324,349 | 3,912 | 0 |
| nvarc_full | 1,785,960 | 0 | — | — | 1,785,960 |
| arc2_evaluation6 | 720 | 0 | — | — | 720 |
| Total | 3,256,201 | 1,101,555 | 363,512 | 4,454 | 1,786,680 |

五個 filtered HF sources 合計 3,162,375,443 compact input tokens，
1,372,921,383 supervised tokens；HF files 合計 3,314,294,884 bytes。
這是 corpus accounting，並非已訓練或授權的 token 數。
每個來源保存 closed HF member hashes、逐筆 `parent_ids` lineage、quarantine
原因、record/token counts、length histogram 和完整來源 row index。

本機材料位置：

- 原資料：`.irisx/nvarc-data/raw/{augmented-v1,synthetic-v1}/`
- 解包：`.irisx/nvarc-data/extracted/augmented-v1/`
- Parent catalog：`.irisx/nvarc-data/parent-catalog.json`
- 處理：`.irisx/nvarc-data/processed-20261001-001/`
- 合格 HF：該處理目錄下的 `augmented/<source>/hf/`
- Lineage/quarantine：各 `augmented/<source>/{lineage,quarantine}.jsonl`

## 就緒程度與查核

資料下載與五來源 HF preparation 已完成；原 six-source clean-research gate
仍為 false。`nvarc_full` 全部含 evaluation ancestor，不能假裝為乾淨來源，
也不能用其他來源填補來宣稱原方法完整。雙親 `parent_ids` 不能被壓成假的
單一 `parent_id` 以滿足舊 freezer。既有六來源契約與凍結 artifacts 保持不變。
新訓練前仍需審定乾淨 method/data 配方、完整 lineage store、跨來源 semantic
overlap 與 distributed/GPU 資源驗證。這些 dev tasks 不稱為 fresh holdout。

資料管線的七項測試通過，涵蓋 ZIP 安全、雙親排除、token accounting、真實
HF 篩選/順序與上游 loader，以及重算 metadata hashes 後的假 parent 拒絕。
獨立驗證已通過全部 1,101,555 筆 lineage 的順序、parent/exposure、token counts
與 HF closed inventories；真正上游 SFT loader 每來源抽查 32 筆，共 160 筆。
以最終 path guard 再查兩包原 ZIP 的全部 member names，原 ZIP digests 保持一致。

- 新資料管線：7 tests，0.595 秒，零 skip，通過。
- Repository `--all`：299 tests，424.471 秒，四個既有 optional skips，通過。
- Strict ML profile：38 tests，539.525 秒，零 skip，通過。
- Method audit：source/reference verified；corpus、bounded-training、full-method、
  full-scale SFT 與 quality comparison gates 仍為 false。

Terminal bindings（相對於 `.irisx/nvarc-data/`，SHA-256）：

| Artifact | SHA-256 |
| --- | --- |
| `completion-001.json` | `587c31853afc46430ad6b3426575e69d3848bc2c701605b8be32726497b08a20` |
| `parent-catalog.json` | `4fc2ec18a817adc2e4f54122b8feafec5d78c91df5a12e337be4b21005d23c4f` |
| `processed-20261001-001/manifest.json` | `102e3d579ef5742c4afc84c5282332bd6b3d9772086c8cac2454986fb4c9dfe3` |
| `processed-20261001-001/augmented/audit.json` | `2782c1b7ca61bd1cc1a2070ce65b31d279097c4b6d344212d518228cec9f009f` |
| `verification-001.json` | `0c40769f427120b4680dc41259e194c6f7476a31522b6dafffc075106fc8c422` |
| `tests-004.log` | `2116f4370051c25cd20121dc07a8287ff42062d48d8d916400dba66fbd2e1fd9` |
| `repository-check-001.log` | `f02633ade11626e7ed4dd196b8058b4355f03111f9cbb8623deb678866e0239f` |
| `strict-ml-001.log` | `098c86a5429a8acd9fd032085927add8942f25fac5f0213fa4f25c3d1115b317` |

Completion manifest 另外綁定兩份完整 ZIP inventories、acquisition ledger、
retained-archive verification、synthetic audit、source manifest 與 method readiness。

本次沒有 real-data training、外部 teacher/model call、Dataset mutation、kernel
save/run、監控、execution-output retrieval、scoring 或 promotion；付費 USD 0。
約 42 GB 的 artifacts dataset 沒有下載。
