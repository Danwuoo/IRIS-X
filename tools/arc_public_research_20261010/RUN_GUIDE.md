# PUBLIC120 執行指南

## Notebook 與設定

使用新 PUBLIC120 notebook。舊 consolidated v4 與其結果保持原樣。
第一次執行建議使用全新 kernel / runtime：

- MANUAL_START = True
- ENABLE_MODEL = True：執行 raw／strict 模型比較；False 只執行 CPU 研究基線
- PROFILE = 'PUBLIC120'
- RESUME = False
- OUTPUT_ROOT = 'irisx-public120-20261010-run001'，每次更換全新名稱
- SESSION_SECONDS = 7200
- MODEL_CONFIG = None、CODE_ROOT = None、DATA_ROOT = None：使用精確 Dataset mount 探索
- Internet 關閉；GPU 模型路徑選既定 G4 RTX PRO 6000 Blackwell，48 CPU

source-only 發布時兩個開關均為 False，GPU／TPU／Internet 均關閉。
若只是按 Run All 而未打開 MANUAL_START，只會顯示 disabled。不要啟動
舊 FULL，也不用另開多個實驗 notebook。這不是訓練，也不是官方競賽 submission。

所需7個獨立固定版本 Dataset：

1. danielwuu/iris-x-public120-code-20261010/1
2. danielwuu/iris-x-public120-data-20261010/1
3. danielwuu/iris-arc-next-runtime/8
4. danielwuu/iris-arc-granite42-8b-offline/2
5. danielwuu/iris-arc-next-cu128-cp312-wheels/1
6. danielwuu/iris-arc-next-cpython312-offline/2
7. danielwuu/iris-arc-granite42-run003-adapter-20261009/1

只接受兩種精確 mount layout：/kaggle/input/<slug> 或
/kaggle/input/datasets/<owner>/<slug>。若 notebook 環境給不同路徑，可明確
填 CODE_ROOT / DATA_ROOT 或 MODEL_CONFIG 的既有五個 explicit_roots；
不做廣泛遞迴搜尋、不使用競賽資料目錄。所有資產仍須通過 manifest/hash。
code Dataset接受原source.zip，或Kaggle自動解壓後的精確root／source子目錄；
要求完整來源inventory與每檔hash，混合模糊layout會拒絕。解壓模式驗證來源bytes，
不聲稱原ZIP bytes仍在mount可讀；console會明列transport mode。

GPU runtime 合约沿用單卡 RTX PRO 6000 Blackwell、至少90GB顯存、compute12.0、
CUDA12.8、sm120、48CPU、至少170GiB RAM，以及原固定driver下限。這些不是
四L4競賽環境的等價聲明；CPU驗證不代表該GPU模型路徑已實測成功。

## 會做多少工作

每次先128個真實受限CPU控制。之後120題各做uniform與shape排名64候選，
共最多15,360次新鮮CPU驗證；不重跑47,720次FULL coverage。模型共規劃240calls，
但真實tokenizer預檢目前只有88題可容納prompt，32題成對context-excluded，
因此最多176次實際模型calls。兩臂排除相同題，沒有截斷。

只用demo全部相符的計畫做query。四政策共最多1,336次query執行；總CPU上限
17,064，session上限7200秒。所有時間與額度包含在同session內，unknown仍計費，
不自動重試。大題／時間不足不會從167測試分母消失。

## 結果與下載

主報告包含四個獨立policy的exact-grid pass@1／pass@2，以及120題補充統計。
CPU-only run的raw／strict沒有模型輸出，會保留空集合與完整分母，不能當模型結果。
模型比較要同時看全167測試及88題／122測試的成對可用範圍。

保留：
- evidence ZIP
- 同run的 post-seal-closure.json
- 最後的 ledger/journal.jsonl
- summary、prediction seal、四個pools與scorer報告（亦在ZIP快照內）

ZIP是停止模型後的封存快照；post-seal closure與最後journal尾端在其後寫入，故須一併
下載以核對完整結案。最後console只顯示小摘要，完整資料在檔案內。

若看到SCORING_BLOCKED，代表預測／停止／封存證據不符合合約，不是0分。
保留失敗證據，不手改ledger／prediction。Partial resume目前明確拒絕；新run用
新OUTPUT_ROOT，切勿把舊來源的結果繼續接上新來源。

## 科學標示

所有報告標記public development exposure、research硬體與model/source/data身份。
competition_gpu_equivalent=false，official competition score=null。公開資料已受
先前開發曝光，不能聲稱未觸碰測試集；既有adapter未使用、沒有訓練。

## 本次自動執行範圍

依owner後續指示，本次另外保留只改三個config值的啟用版本：MANUAL_START=True、
ENABLE_MODEL=True、OUTPUT_ROOT='irisx-public120-20261010-gpu001'。以既有GCP／G4
設定啟動GPU並保留ARC-AGI-3 metadata association，不讀取其題目資料。

操作驗收需active版本provider COMPLETE，加上模型階段、prediction seal、scorer
與最終停止／封存receipt完整；inactive renderer完成不等於實驗成功。若失敗只診斷
與修復操作錯誤，保留前次證據、確認沒有重疊active run，再用新版本與output identity。
完成後停止，不分析分數或比較方法，不進行下一輪研究。
